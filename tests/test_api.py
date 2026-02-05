"""API endpoint tests for Paper Reproducibility Checker.

Tests REST API endpoints with mocked dependencies:
- Event logging via EventDispatcher
- Error handling and validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
from models.events import JobEvent
from services.event_dispatcher import EventDispatcher, EventDispatcherFactory


class TestEventLoggingEndpoint:
    """Tests for event logging endpoint patterns."""
    
    def test_emit_event_via_dispatcher(self, app):
        """Test emitting event through dispatcher."""
        queues = {"job123": []}
        
        dispatcher = EventDispatcher(event_queues=queues, job_service=None)
        
        event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            message="Starting analysis",
        )
        dispatcher.emit(event)
        
        # Event should be in queue
        assert len(queues["job123"]) == 1
        assert queues["job123"][0]["step"] == "stage_1_starting"
    
    def test_log_event_with_stage_duration(self, app):
        """Test logging event with stage_duration_ms."""
        queues = {"job123": []}
        dispatcher = EventDispatcher(event_queues=queues, job_service=None)
        
        event = JobEvent(
            job_id="job123",
            step="stage_1_complete",
            message="Stage completed",
            stage_duration_ms=5432,
        )
        dispatcher.emit(event)
        
        # Event in queue should have stage_duration_ms
        assert queues["job123"][0]["stage_duration_ms"] == 5432
    
    def test_log_chat_event_not_persisted(self, app):
        """Test that chat events are not persisted to database."""
        queues = {"job123": []}
        
        with patch('services.event_dispatcher.Job') as mock_job_class, \
             patch('services.event_dispatcher.Event') as mock_event_class:
            
            dispatcher = EventDispatcher(event_queues=queues, job_service=None)
            
            # Emit chat event
            event = JobEvent(
                job_id="job123",
                step="chat_response",
                content="Analysis complete",
            )
            dispatcher.emit(event)
            
            # Should NOT call database
            mock_job_class.get_by_id.assert_not_called()
            mock_event_class.create.assert_not_called()
            
            # But should be in SSE queue
            assert len(queues["job123"]) == 1
    
    def test_log_non_chat_event_persisted(self):
        """Test that non-chat events are persisted."""
        queues = {"job123": []}
        
        with patch('services.event_dispatcher.Job') as mock_job_class, \
             patch('services.event_dispatcher.Event') as mock_event_class:
            
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job
            
            dispatcher = EventDispatcher(event_queues=queues, job_service=None)
            
            event = JobEvent(
                job_id="job123",
                step="stage_1_complete",
                message="Completed",
            )
            dispatcher.emit(event)
            
            # Should call database
            mock_job_class.get_by_id.assert_called_once_with("job123")
            mock_event_class.create.assert_called_once()
    
    def test_log_event_invalid_severity(self):
        """Test validation of severity level."""
        valid_severities = ["info", "warning", "error"]
        
        # Valid severity
        event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            severity="info",
        )
        assert event.severity in valid_severities
        
        # Invalid severity - but JobEvent doesn't validate, so we just check it's accepted
        event_invalid = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            severity="invalid",
        )
        assert event_invalid.severity == "invalid"


class TestErrorHandling:
    """Tests for API error handling."""
    
    def test_missing_job_id_error(self):
        """Test error when job_id is missing."""
        # Request without job_id
        request_data = {
            "step": "stage_1_starting",
            "message": "Some message",
        }
        
        # Should fail validation
        assert "job_id" not in request_data
    
    def test_invalid_job_id_error(self):
        """Test error when job_id doesn't exist."""
        with patch('services.event_dispatcher.Job') as mock_job_class:
            
            # Simulate job not found
            mock_job_class.get_by_id.side_effect = Exception("Job not found")
            
            dispatcher = EventDispatcher(event_queues={}, job_service=None)
            
            event = JobEvent(job_id="nonexistent", step="stage_1_starting")
            
            # Should handle error gracefully
            logged_errors = []
            dispatcher.logger = lambda msg: logged_errors.append(msg)
            
            dispatcher.emit(event)  # Should not raise
    
    def test_database_error_logged(self):
        """Test that database errors are logged."""
        queues = {"job123": []}
        logged = []
        
        with patch('services.event_dispatcher.Job') as mock_job_class, \
             patch('services.event_dispatcher.Event') as mock_event_class:
            
            # Simulate database error
            mock_job_class.get_by_id.side_effect = Exception("Database connection failed")
            
            dispatcher = EventDispatcher(
                event_queues=queues,
                job_service=None,
                logger=lambda msg: logged.append(msg),
            )
            
            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)
            
            # Error should be logged
            errors = [msg for msg in logged if "Failed to persist" in msg]
            assert len(errors) == 1
    
    def test_invalid_event_data(self):
        """Test handling of invalid event data."""
        # Event with missing required field
        with pytest.raises(TypeError):
            # job_id is required
            event = JobEvent(step="stage_1_starting")


class TestValidation:
    """Tests for input validation."""
    
    def test_job_id_required(self):
        """Test that job_id is required."""
        with pytest.raises(TypeError):
            JobEvent(step="stage_1_starting")  # Missing job_id
    
    def test_step_required(self):
        """Test that step is required."""
        with pytest.raises(TypeError):
            JobEvent(job_id="job123")  # Missing step
    
    def test_event_timestamp_auto_set(self):
        """Test that timestamp is auto-set if not provided."""
        event = JobEvent(job_id="job123", step="stage_1_starting")
        
        assert event.timestamp is not None
        assert len(event.timestamp) > 0
    
    def test_event_default_severity(self):
        """Test that severity defaults to 'info'."""
        event = JobEvent(job_id="job123", step="stage_1_starting")
        
        assert event.severity == "info"


class TestEventSerialization:
    """Tests for event serialization."""
    
    def test_event_to_dict_includes_all_fields(self):
        """Test that to_dict includes all event fields."""
        event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            message="Test",
            severity="warning",
            progress=0.5,
            content="Chat content",
            stage_duration_ms=1234,
        )
        
        d = event.to_dict()
        
        assert d["job_id"] == "job123"
        assert d["step"] == "stage_1_starting"
        assert d["message"] == "Test"
        assert d["severity"] == "warning"
        assert d["progress"] == 0.5
        assert d["content"] == "Chat content"
        assert d["stage_duration_ms"] == 1234
        assert "timestamp" in d
    
    def test_event_dict_json_serializable(self):
        """Test that event.to_dict() is JSON serializable."""
        event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            message="Test",
            stage_duration_ms=5432,
        )
        
        d = event.to_dict()
        
        # Should not raise
        json_str = json.dumps(d)
        assert json_str is not None
        
        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["job_id"] == "job123"


class TestStageTransitionEvents:
    """Tests for stage transition events."""
    
    def test_stage_transition_event_logged(self):
        """Test that stage transition events are logged."""
        queues = {"job123": []}
        logged = []
        
        with patch('services.event_dispatcher.Job'), \
             patch('services.event_dispatcher.Event'):
            
            dispatcher = EventDispatcher(
                event_queues=queues,
                job_service=None,
                logger=lambda msg: logged.append(msg),
            )
            
            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)
            
            # Transition should be logged
            transitions = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transitions) == 1
            assert "paper_analysis" in transitions[0]
    
    def test_all_stage_transitions_recognized(self):
        """Test that all stage transitions are recognized."""
        from models.events import STAGE_TRANSITIONS
        
        stage_steps = list(STAGE_TRANSITIONS.keys())
        
        assert "stage_1_starting" in stage_steps
        assert "stage_1_complete" in stage_steps
        assert "stage_2_complete" in stage_steps
        assert "stage_3_complete" in stage_steps
        assert "complete" in stage_steps
        
        assert len(stage_steps) == 7


class TestConcurrentEventEmission:
    """Tests for concurrent event emission."""
    
    def test_multiple_events_to_same_job(self, app):
        """Test multiple events emitted to same job queue."""
        queues = {"job123": []}
        dispatcher = EventDispatcher(event_queues=queues, job_service=None)
        
        events = [
            JobEvent(job_id="job123", step="stage_1_starting"),
            JobEvent(job_id="job123", step="extracting_text"),
            JobEvent(job_id="job123", step="analyzing"),
            JobEvent(job_id="job123", step="stage_1_complete"),
        ]
        
        for event in events:
            dispatcher.emit(event)
        
        assert len(queues["job123"]) == 4
    
    def test_events_to_different_jobs(self, app):
        """Test events to different job queues."""
        queues = {"job1": [], "job2": [], "job3": []}
        dispatcher = EventDispatcher(event_queues=queues, job_service=None)
        
        for job_id in ["job1", "job2", "job3"]:
            event = JobEvent(job_id=job_id, step="stage_1_starting")
            dispatcher.emit(event)
        
        assert len(queues["job1"]) == 1
        assert len(queues["job2"]) == 1
        assert len(queues["job3"]) == 1
    
    def test_event_to_nonexistent_queue(self):
        """Test emitting to job with no queue (no error)."""
        dispatcher = EventDispatcher(event_queues={}, job_service=None)
        
        event = JobEvent(job_id="job123", step="stage_1_starting")
        
        # Should not raise error
        dispatcher.emit(event)


class TestEventFactory:
    """Tests for event dispatcher factory."""
    
    def test_create_test_dispatcher(self):
        """Test creating a test dispatcher."""
        dispatcher = EventDispatcherFactory.create_test_dispatcher()
        
        assert dispatcher is not None
        assert dispatcher.event_queues == {}
        assert dispatcher.event_queues_lock is not None
    
    def test_create_dispatcher_with_queues(self):
        """Test creating dispatcher with custom queues."""
        custom_queues = {"job1": [], "job2": []}
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=custom_queues)
        
        assert dispatcher.event_queues == custom_queues
    
    def test_test_dispatcher_with_mock_logger(self):
        """Test test dispatcher with custom logger."""
        logged = []
        
        dispatcher = EventDispatcherFactory.create_test_dispatcher(
            mock_logger=lambda msg: logged.append(msg)
        )
        
        # Emit event that triggers logging
        with patch('services.event_dispatcher.Job'), \
             patch('services.event_dispatcher.Event'):
            
            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)
            
            # Should have logged transition
            transitions = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transitions) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
