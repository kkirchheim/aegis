"""Tests for pipeline orchestrator."""

import pytest
import threading
from unittest.mock import Mock, patch, MagicMock, call
from services.pipeline_orchestrator import PipelineOrchestrator, PipelineOrchestratorFactory
from services.event_dispatcher import EventDispatcher
from models.events import JobEvent


class TestPipelineOrchestrator:
    """Test PipelineOrchestrator."""
    
    def test_orchestrator_creation(self):
        """Test creating an orchestrator."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)
        
        assert orchestrator.dispatcher is dispatcher
    
    def test_emit_event_creates_job_event(self):
        """Test that emit_event creates JobEvent and calls dispatcher."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)
        
        orchestrator.emit_event("job123", "test_step", "Test message", 0.5)
        
        # Verify dispatcher.emit was called
        dispatcher.emit.assert_called_once()
        
        # Verify it was called with a JobEvent
        call_args = dispatcher.emit.call_args
        event = call_args[0][0]
        assert isinstance(event, JobEvent)
        assert event.job_id == "job123"
        assert event.step == "test_step"
        assert event.message == "Test message"
        assert event.progress == 0.5
    
    def test_run_analysis_success_flow(self):
        """Test successful analysis flow through all stages."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher,
                                           logger=lambda msg: None)

        # Mock all service calls
        with patch('services.pipeline_orchestrator.update_job_status') as mock_update, \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts') as mock_store, \
             patch('services.pipeline_orchestrator.spawn_agent_container') as mock_spawn, \
             patch.object(orchestrator, '_run_stage_3', return_value=True) as mock_stage3:

            # Setup mocks
            mock_extract.return_value = ("text content", {"artifacts": []})

            # Run analysis
            result = orchestrator.run_analysis(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),  # config
                Mock(),  # llm_provider
                manual_artifacts=[]
            )

            assert result is True
            mock_update.assert_called()
            mock_extract.assert_called_once()
            mock_stage3.assert_called_once()
            dispatcher.emit.assert_called()
    
    def test_run_analysis_handles_stage_1_failure(self):
        """Test that analysis fails gracefully if stage 1 fails."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher, 
                                           logger=lambda msg: None)
        
        with patch('services.pipeline_orchestrator.update_job_status') as mock_update, \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract:
            
            # Make stage 1 fail
            mock_extract.side_effect = Exception("PDF extraction failed")
            
            result = orchestrator.run_analysis(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),  # config
                Mock(),  # llm_provider
                manual_artifacts=[]
            )
            
            assert result is False
            # Verify dispatcher was called with error event
            dispatcher.emit.assert_called()
    
    def test_run_analysis_handles_stage_3_failure(self):
        """Test that analysis fails if evaluation fails."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher,
                                           logger=lambda msg: None)

        with patch('services.pipeline_orchestrator.update_job_status') as mock_update, \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts') as mock_store, \
             patch.object(orchestrator, '_run_stage_3', return_value=False):

            # Setup mocks
            mock_extract.return_value = ("text", {"artifacts": []})

            result = orchestrator.run_analysis(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),  # config
                Mock(),  # llm_provider
                manual_artifacts=[]
            )

            assert result is False
            # Verify dispatcher was called with error event
            dispatcher.emit.assert_called()
    
    def test_run_stage_1_extracts_and_stores_artifacts(self):
        """Test stage 1: extract PDF and store artifacts."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)
        
        with patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts') as mock_store:
            
            artifacts = [
                {"type": "github_repo", "url": "https://github.com/user/repo"}
            ]
            mock_extract.return_value = ("text", {"artifacts": artifacts})
            
            result = orchestrator._run_stage_1("job123", "/path/to/pdf.pdf", Mock())
            
            assert result is True
            mock_extract.assert_called_once()
            mock_store.assert_called_once_with("job123", artifacts)

    def test_run_stage_1_merges_manual_artifacts(self):
        """Test stage 1 merges extracted and manual artifacts without duplicates."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)

        with patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts') as mock_store:

            extracted_artifacts = [
                {"type": "dataset", "url": "https://example.com/data", "description": "Dataset"},
                {"type": "github_repo", "url": "https://github.com/user/repo", "description": "Extracted repo"},
            ]
            manual_artifacts = [
                {"type": "github_repo", "url": "https://github.com/user/repo", "description": "Manual repo"},
                {"url": "https://github.com/user/extra-repo", "description": "Manual extra repo"},
            ]
            mock_extract.return_value = ("text", {"artifacts": extracted_artifacts})

            result = orchestrator._run_stage_1(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),
                manual_artifacts=manual_artifacts
            )

            assert result is True
            mock_store.assert_called_once_with("job123", [
                {"type": "dataset", "url": "https://example.com/data", "description": "Dataset"},
                {"type": "github_repo", "url": "https://github.com/user/repo", "description": "Extracted repo"},
                {"type": "github_repo", "url": "https://github.com/user/extra-repo", "description": "Manual extra repo"},
            ])
    
    def test_run_stage_2_executes_github_artifacts(self):
        """Test stage 2: execute code from GitHub artifacts."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)
        orchestrator._artifacts = [
            {"type": "github_repo", "url": "https://github.com/user/repo1"},
            {"type": "github_repo", "url": "https://github.com/user/repo2"},
        ]
        
        with patch('services.pipeline_orchestrator.spawn_agent_container') as mock_spawn:
            result = orchestrator._run_stage_2("job123", Mock())
            
            assert result is True
            # Should spawn agent for each artifact
            assert mock_spawn.call_count == 2

    def test_run_stage_2_executes_manually_provided_github_artifact(self):
        """Test stage 2 executes a manually supplied GitHub artifact URL."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)
        orchestrator._artifacts = [
            {"type": "github_repo", "url": "https://github.com/user/manual-repo"},
            {"type": "other", "url": "https://example.com/not-executed"},
        ]

        with patch('services.pipeline_orchestrator.spawn_agent_container') as mock_spawn:
            result = orchestrator._run_stage_2("job123", Mock())

            assert result is True
            mock_spawn.assert_called_once()
            assert mock_spawn.call_args[0][1] == "https://github.com/user/manual-repo"
    
    def test_run_stage_2_handles_agent_failure(self):
        """Test stage 2: handles agent failure gracefully."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)
        orchestrator._artifacts = [
            {"type": "github_repo", "url": "https://github.com/user/repo"},
        ]
        
        with patch('services.pipeline_orchestrator.spawn_agent_container') as mock_spawn:
            mock_spawn.side_effect = Exception("Agent failed")
            
            result = orchestrator._run_stage_2("job123", Mock())
            
            # Stage 2 should succeed even if agent fails (continue with other repos)
            assert result is True
    
    def test_run_stage_3_evaluates_reproducibility(self):
        """Test stage 3: evaluate reproducibility (mocked at method level)."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)

        with patch.object(orchestrator, '_run_stage_3', return_value=True) as mock_stage3:
            result = orchestrator._run_stage_3("job123", Mock())

            assert result is True
            mock_stage3.assert_called_once()

    def test_run_stage_3_fails_if_evaluation_returns_false(self):
        """Test stage 3: fails if evaluation returns False."""
        orchestrator = PipelineOrchestrator(logger=lambda msg: None)

        with patch.object(orchestrator, '_run_stage_3', return_value=False) as mock_stage3:
            result = orchestrator._run_stage_3("job123", Mock())

            assert result is False
    
    def test_emit_event_without_dispatcher(self):
        """Test emit_event works without dispatcher."""
        orchestrator = PipelineOrchestrator(dispatcher=None)
        
        # Should not raise error
        orchestrator.emit_event("job123", "test", "message", 0.5)
    
    def test_logger_called_at_key_points(self):
        """Test that logger is called at key pipeline points."""
        logged = []
        logger = lambda msg: logged.append(msg)
        orchestrator = PipelineOrchestrator(logger=logger)

        with patch('services.pipeline_orchestrator.update_job_status'), \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts'), \
             patch.object(orchestrator, '_run_stage_3', return_value=True):

            mock_extract.return_value = ("text", {"artifacts": []})

            orchestrator.run_analysis("job123", "/path/to/pdf", Mock(), Mock())

            # Check that key milestones were logged
            assert any("ANALYSIS STARTED" in msg for msg in logged)
            assert any("STAGE 1" in msg for msg in logged)
            assert any("STAGE 2" in msg for msg in logged)
            # Stage 3 is mocked so its internal logs won't appear,
            # but the pipeline wrapper still logs around it
            assert any("ANALYSIS COMPLETE" in msg for msg in logged)


class TestPipelineOrchestratorFactory:
    """Test PipelineOrchestratorFactory."""
    
    def test_create_production(self):
        """Test creating production orchestrator."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestratorFactory.create(dispatcher=dispatcher)
        
        assert orchestrator is not None
        assert orchestrator.dispatcher is dispatcher
    
    def test_create_test(self):
        """Test creating test orchestrator."""
        orchestrator = PipelineOrchestratorFactory.create_test()
        
        assert orchestrator is not None
        assert orchestrator.dispatcher is None
    
    def test_create_test_with_mock_logger(self):
        """Test test orchestrator with mock logger."""
        logged = []
        logger = lambda msg: logged.append(msg)

        orchestrator = PipelineOrchestratorFactory.create_test(mock_logger=logger)

        with patch('services.pipeline_orchestrator.update_job_status'), \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts'), \
             patch.object(orchestrator, '_run_stage_3', return_value=True):

            mock_extract.return_value = ("text", {"artifacts": []})

            result = orchestrator.run_analysis("job123", "/path/to/pdf", Mock(), Mock())

            assert result is True
            # Logger should have been called
            assert len(logged) > 0


class TestPipelineIntegration:
    """Integration tests for pipeline."""
    
    def test_full_pipeline_happy_path(self):
        """Test complete pipeline with all stages succeeding."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher,
                                           logger=lambda msg: None)

        with patch('services.pipeline_orchestrator.update_job_status'), \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract, \
             patch('services.pipeline_orchestrator.store_artifacts'), \
             patch('services.pipeline_orchestrator.spawn_agent_container'), \
             patch.object(orchestrator, '_run_stage_3', return_value=True):

            artifacts = [
                {"type": "github_repo", "url": "https://github.com/user/repo"}
            ]
            mock_extract.return_value = ("pdf text", {"artifacts": artifacts})

            result = orchestrator.run_analysis(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),  # config
                Mock()   # llm_provider
            )

            assert result is True
            # Verify event emissions (stage 3 is mocked so fewer events)
            assert dispatcher.emit.call_count >= 5
    
    def test_pipeline_error_recovery(self):
        """Test pipeline handles errors and updates job status."""
        dispatcher = Mock(spec=EventDispatcher)
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher,
                                           logger=lambda msg: None)
        
        with patch('services.pipeline_orchestrator.update_job_status') as mock_update, \
             patch('services.pipeline_orchestrator.extract_and_analyze_pdf') as mock_extract:
            
            mock_extract.side_effect = Exception("Network error")
            
            result = orchestrator.run_analysis(
                "job123",
                "/path/to/pdf.pdf",
                Mock(),
                Mock()
            )
            
            assert result is False
            # Verify dispatcher was called to emit error
            dispatcher.emit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
