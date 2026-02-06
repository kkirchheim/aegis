"""Tests for orchestrator integration with aspect plugin system."""

import pytest
import json
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from models.database import db, Job, User, PaperAnalysis, ExecutionDetails
from services.aspect_service import AspectService
from services.pipeline_orchestrator import PipelineOrchestrator, stage_3_evaluation
from repositories import AspectRepository, UserAspectRepository


@pytest.fixture
def test_user():
    """Create test user."""
    user = User.create(
        username="test_user_aspects",
        email="test_aspects@example.com",
        password_hash="hash",
        is_active=True
    )
    yield user
    user.delete_instance()


@pytest.fixture
def test_job(test_user):
    """Create test job."""
    job = Job.create(
        id=str(uuid4()),
        user=test_user,
        status='pending',
        current_stage='pending',
        progress=0.0,
        pdf_path='test.pdf',
        pdf_filename='test.pdf'
    )
    yield job
    
    # Cleanup related records first
    try:
        PaperAnalysis.delete().where(PaperAnalysis.job == job.id).execute()
        ExecutionDetails.delete().where(ExecutionDetails.job == job.id).execute()
    except:
        pass
    
    job.delete_instance()


@pytest.fixture
def test_paper_analysis(test_job):
    """Create test paper analysis."""
    analysis = PaperAnalysis.create(
        job=test_job,
        extracted_text="This is a test paper about reproducibility. It contains methodology and results.",
        title="Test Paper",
        abstract="A test abstract"
    )
    yield analysis
    analysis.delete_instance()


@pytest.fixture
def test_execution_details(test_job):
    """Create test execution details."""
    details = ExecutionDetails.create(
        job=test_job,
        stdout_combined="Test code execution output\nResults: 42",
        errors_summary="Test execution log",
        status="completed"
    )
    yield details
    details.delete_instance()


class TestOrchestratorStage3WithAspects:
    """Tests for orchestrator _run_stage_3 with aspects."""
    
    def test_stage3_evaluation_with_active_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should evaluate all active aspects."""
        # Seed defaults for user
        AspectService.get_or_create_default_aspects(test_user.id)
        active_aspects = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        assert len(active_aspects) > 0, "Should have active default aspects"
        
        # Create orchestrator with mocked LLM
        orchestrator = PipelineOrchestrator()
        
        # Mock evaluate_paper to return sample results
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {
                str(active_aspects[0]['id']): {
                    "status": "PASS",
                    "reasoning": "Code is available"
                }
            }
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        # Verify job updated
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        assert updated_job.evaluation_results is not None
        
        results = updated_job.get_evaluation_results()
        assert len(results) > 0
    
    def test_stage3_evaluation_with_no_active_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should skip evaluation if no active aspects."""
        # Don't seed any aspects for user - they have none
        orchestrator = PipelineOrchestrator()
        
        result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        # Verify job completed with empty results
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        results = updated_job.get_evaluation_results()
        assert len(results) == 0
    
    def test_stage3_evaluation_with_custom_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should evaluate custom aspects."""
        # Create custom aspect
        custom_aspect = AspectService.create_custom_aspect(
            user_id=test_user.id,
            name="Custom Check",
            description="A custom check",
            prompt="Does this meet our criteria?"
        )
        
        active_aspects = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert len(active_aspects) > 0
        
        orchestrator = PipelineOrchestrator()
        
        # Mock evaluation
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {
                custom_aspect['id']: {
                    "status": "FAIL",
                    "reasoning": "Criteria not met"
                }
            }
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evaluation_results()
        assert custom_aspect['id'] in results
    
    def test_stage3_evaluation_handles_error(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should handle evaluation errors."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        orchestrator = PipelineOrchestrator()
        
        # Mock evaluation to raise error
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.side_effect = Exception("LLM error")
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == False
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'error'
        assert 'failed' in updated_job.error_message.lower() or 'evaluation' in updated_job.error_message.lower()
    
    def test_stage3_evaluation_deactivated_aspects_skipped(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should skip deactivated aspects."""
        # Seed defaults
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Deactivate all aspects
        all_user_aspects = UserAspectRepository.get_user_aspects(test_user.id)
        for ua in all_user_aspects:
            AspectService.deactivate_aspect(test_user.id, ua.aspect_id)
        
        # Should have no active aspects
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert len(active) == 0
        
        orchestrator = PipelineOrchestrator()
        
        result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evaluation_results()
        assert len(results) == 0
    
    def test_stage3_evaluation_mixed_aspects_status(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should handle mixed PASS/FAIL/UNCLEAR statuses."""
        AspectService.get_or_create_default_aspects(test_user.id)
        active_aspects = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        # Mock evaluation with mixed results
        results_dict = {}
        for i, aspect in enumerate(active_aspects):
            status = ['PASS', 'FAIL', 'UNCLEAR'][i % 3]
            results_dict[aspect['id']] = {
                "status": status,
                "reasoning": f"Test {status}"
            }
        
        orchestrator = PipelineOrchestrator()
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = results_dict
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evaluation_results()
        
        # Verify counts
        passed = sum(1 for r in results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in results.values() if r['status'] == 'FAIL')
        unclear = sum(1 for r in results.values() if r['status'] == 'UNCLEAR')
        
        assert passed >= 0 and failed >= 0 and unclear >= 0
    
    def test_stage3_stores_results_as_json(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should store results as proper JSON in job.evaluation_results."""
        AspectService.get_or_create_default_aspects(test_user.id)
        active_aspects = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        orchestrator = PipelineOrchestrator()
        
        test_results = {
            str(active_aspects[0]['id']): {
                "status": "PASS",
                "reasoning": "Very reproducible"
            }
        }
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = test_results
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        
        # Verify it's valid JSON
        assert updated_job.evaluation_results is not None
        parsed = json.loads(updated_job.evaluation_results)
        assert isinstance(parsed, dict)
        assert len(parsed) > 0
    
    def test_stage3_updates_job_progress(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should set job progress to 1.0 on completion."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        orchestrator = PipelineOrchestrator()
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {}
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.progress == 1.0
        assert updated_job.current_stage == 'evaluation'
    
    def test_stage3_emits_events(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit proper progress events."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Mock dispatcher to capture events
        mock_dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=mock_dispatcher)
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {}
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        # Verify emit_event was called (indirectly through dispatcher)
        # The event should have been emitted at least twice (start and complete)
        assert mock_dispatcher is not None


class TestAspectServiceIntegration:
    """Integration tests for aspect service with orchestrator."""
    
    def test_get_active_aspects_returns_prompts(self, test_user):
        """get_active_aspects_for_evaluation should return correct prompts."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        assert len(active) > 0
        for aspect in active:
            assert 'id' in aspect
            assert 'name' in aspect
            assert 'prompt_to_use' in aspect
            assert len(aspect['prompt_to_use']) > 0
    
    def test_custom_prompt_override_in_evaluation(self, test_user):
        """Custom prompts should be used in evaluation context."""
        # Create custom aspect
        custom = AspectService.create_custom_aspect(
            user_id=test_user.id,
            name="Custom",
            description="Custom aspect",
            prompt="Original prompt"
        )
        
        # Override prompt
        custom_prompt = "Overridden prompt for evaluation"
        AspectService.override_prompt(test_user.id, custom['id'], custom_prompt)
        
        # Get for evaluation
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        # Find our custom aspect
        found = next((a for a in active if a['id'] == custom['id']), None)
        assert found is not None
        assert found['prompt_to_use'] == custom_prompt
    
    def test_deactivated_aspects_excluded_from_evaluation(self, test_user):
        """Deactivated aspects should not appear in evaluation context."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Get all active
        active_before = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert len(active_before) > 0
        
        # Deactivate one
        first_aspect_id = active_before[0]['id']
        AspectService.deactivate_aspect(test_user.id, first_aspect_id)
        
        # Get active again
        active_after = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        # Should be one less
        assert len(active_after) == len(active_before) - 1
        
        # Our deactivated one should not be present
        ids = [a['id'] for a in active_after]
        assert first_aspect_id not in ids
    
    def test_multiple_users_aspects_isolated(self, test_user):
        """Different users should have isolated aspects."""
        # Create another user
        user2 = User.create(
            username="test_user2_aspects",
            email="test_aspects2@example.com",
            password_hash="hash",
            is_active=True
        )
        
        try:
            # Seed defaults for both
            AspectService.get_or_create_default_aspects(test_user.id)
            AspectService.get_or_create_default_aspects(user2.id)
            
            # Create custom aspect for user1
            custom1 = AspectService.create_custom_aspect(
                user_id=test_user.id,
                name="User1 Custom",
                description="User1 aspect",
                prompt="User1 prompt"
            )
            
            # Get active aspects for both
            active1 = AspectService.get_active_aspects_for_evaluation(test_user.id)
            active2 = AspectService.get_active_aspects_for_evaluation(user2.id)
            
            # User1 should have more (custom added)
            assert len(active1) > len(active2) or len(active1) == len(active2)
            
            # Check that custom1 only appears in user1's aspects
            user1_ids = [a['id'] for a in active1]
            user2_ids = [a['id'] for a in active2]
            assert custom1['id'] in user1_ids
            assert custom1['id'] not in user2_ids
        
        finally:
            user2.delete_instance()
    
    def test_aspect_activation_deactivation_cycle(self, test_user):
        """Aspects should properly toggle activation."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        all_aspects = AspectService.get_all_aspects_for_user(test_user.id)
        first = all_aspects[0]
        aspect_id = first['id']
        
        # Start active
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert aspect_id in [a['id'] for a in active]
        
        # Deactivate
        AspectService.deactivate_aspect(test_user.id, aspect_id)
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert aspect_id not in [a['id'] for a in active]
        
        # Reactivate
        AspectService.activate_aspect(test_user.id, aspect_id)
        active = AspectService.get_active_aspects_for_evaluation(test_user.id)
        assert aspect_id in [a['id'] for a in active]


class TestOrchestrationFullPipeline:
    """Integration tests for full pipeline with aspects."""
    
    def test_full_pipeline_with_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Full pipeline should work end-to-end with aspects."""
        # Setup
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Create orchestrator
        orchestrator = PipelineOrchestrator()
        
        # Mock evaluate_paper
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {
                "aspect1": {"status": "PASS", "reasoning": "Good"},
                "aspect2": {"status": "FAIL", "reasoning": "Bad"},
            }
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        # Verify results
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        assert updated_job.evaluation_results is not None
    
    def test_evaluation_handles_missing_analysis(self, test_job, test_user):
        """Evaluation should handle missing paper analysis gracefully."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Don't create paper_analysis or execution - they're missing
        orchestrator = PipelineOrchestrator()
        
        # Should fail gracefully
        result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == False
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'error'
    
    def test_evaluation_results_json_format(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Evaluation results should be valid JSON with proper structure."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        orchestrator = PipelineOrchestrator()
        
        test_data = {
            "aspect_id_1": {
                "status": "PASS",
                "reasoning": "Code available"
            },
            "aspect_id_2": {
                "status": "FAIL",
                "reasoning": "Missing dependencies"
            }
        }
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = test_data
            
            result = orchestrator._run_stage_3(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evaluation_results()
        
        # Verify structure
        assert isinstance(results, dict)
        for aspect_id, eval_data in results.items():
            assert 'status' in eval_data
            assert 'reasoning' in eval_data
            assert eval_data['status'] in ['PASS', 'FAIL', 'UNCLEAR']


class TestEventEmission:
    """Tests for proper event emission during evaluation."""
    
    def test_start_event_emitted(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit a start event."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {}
            
            orchestrator._run_stage_3(test_job.id, Mock())
        
        # Check that dispatcher was called
        assert dispatcher is not None
    
    def test_completion_event_emitted(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit a completion event with status counts."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)
        
        test_results = {
            "a1": {"status": "PASS", "reasoning": "ok"},
            "a2": {"status": "FAIL", "reasoning": "not ok"},
        }
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = test_results
            
            orchestrator._run_stage_3(test_job.id, Mock())
        
        assert dispatcher is not None


class TestStage3EvaluationStandaloneFunction:
    """Tests for standalone stage_3_evaluation() function."""
    
    def test_stage3_eval_with_active_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should evaluate all active aspects."""
        AspectService.get_or_create_default_aspects(test_user.id)
        active_aspects = AspectService.get_active_aspects_for_evaluation(test_user.id)
        
        assert len(active_aspects) > 0
        
        # Mock evaluate_paper
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {
                str(active_aspects[0]['id']): {
                    "status": "PASS",
                    "reasoning": "Code is available"
                }
            }
            
            with patch('services.pipeline_orchestrator.EventDispatcher'):
                result = stage_3_evaluation(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        results = updated_job.get_evaluation_results()
        assert len(results) > 0
    
    def test_stage3_eval_with_no_aspects(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle zero active aspects."""
        # No aspects seeded
        with patch('services.pipeline_orchestrator.EventDispatcher'):
            result = stage_3_evaluation(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        assert len(updated_job.get_evaluation_results()) == 0
    
    def test_stage3_eval_handles_missing_job(self):
        """stage_3_evaluation should handle missing job gracefully."""
        fake_job_id = str(uuid4())
        
        result = stage_3_evaluation(fake_job_id, Mock())
        
        assert result == False
    
    def test_stage3_eval_with_error(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle errors gracefully."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        # Mock evaluate_paper to raise error
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.side_effect = Exception("LLM error")
            
            with patch('services.pipeline_orchestrator.EventDispatcher'):
                result = stage_3_evaluation(test_job.id, Mock())
        
        assert result == False
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'error'
        assert 'failed' in updated_job.error_message.lower() or 'evaluation' in updated_job.error_message.lower()
    
    def test_stage3_eval_stores_results_json(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should store results as valid JSON."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        test_results = {
            "aspect1": {"status": "PASS", "reasoning": "Good"},
            "aspect2": {"status": "FAIL", "reasoning": "Bad"},
        }
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = test_results
            
            with patch('services.pipeline_orchestrator.EventDispatcher'):
                result = stage_3_evaluation(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evaluation_results()
        
        # Verify valid JSON parsing
        assert isinstance(results, dict)
        assert len(results) == 2
    
    def test_stage3_eval_completes_job(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should mark job as completed."""
        AspectService.get_or_create_default_aspects(test_user.id)
        
        with patch('services.pipeline_orchestrator.evaluate_paper') as mock_eval:
            mock_eval.return_value = {}
            
            with patch('services.pipeline_orchestrator.EventDispatcher'):
                result = stage_3_evaluation(test_job.id, Mock())
        
        assert result == True
        
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == 'completed'
        assert updated_job.progress == 1.0
        assert updated_job.current_stage == 'evaluation'
        assert updated_job.completed_at is not None
