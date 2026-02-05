"""Integration tests for EventDispatcher using real production objects.

These tests use the ACTUAL EventDispatcher from blueprints/jobs.py
and verify end-to-end that events actually update the database.

This catches bugs like:
- Dispatcher not initialized with required dependencies
- Stage transitions not calling update_job_status
- Progress values not persisting to database
"""

import pytest
from models.database import Job, Event
from models.events import JobEvent, STAGE_TRANSITIONS
from services.job_service import create_job


class TestEventDispatcherIntegration:
    """Integration tests using REAL EventDispatcher from production."""
    
    @pytest.fixture
    def real_dispatcher(self, app):
        """Get the REAL dispatcher from production code."""
        from blueprints.jobs import _dispatcher
        return _dispatcher
    
    def test_stage_transition_event_updates_database(self, peewee_test_db, app, real_dispatcher):
        """CRITICAL: Stage transition events MUST update database.
        
        This would have caught the bug where EventDispatcher had no job_service.
        """
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # Emit stage transition event with progress
            event = JobEvent(
                job_id=job_id,
                step="stage_1_complete",
                message="Stage 1 done",
                progress=0.33
            )
            
            # EMIT through real dispatcher
            real_dispatcher.emit(event)
            
            # Check database - this is the integration test
            job = Job.get_by_id(job_id)
            
            # These assertions would FAIL if dispatcher wasn't updating DB
            assert job.current_stage == "code_execution", \
                f"Stage not updated! Got: {job.current_stage}"
            assert job.progress == 0.33, \
                f"Progress not saved! Got: {job.progress}"
            assert job.status == "processing", \
                f"Status not updated! Got: {job.status}"
    
    def test_stage_transitions_through_full_pipeline(self, peewee_test_db, app, real_dispatcher):
        """Test full pipeline: stage transitions should update database at each step."""
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # Stage 1 transition
            event1 = JobEvent(job_id=job_id, step="stage_1_complete", 
                             progress=0.33, message="Stage 1 done")
            real_dispatcher.emit(event1)
            job = Job.get_by_id(job_id)
            assert job.progress == 0.33, f"After stage 1: progress={job.progress}"
            assert job.current_stage == "code_execution"
            
            # Stage 2 transition
            event2 = JobEvent(job_id=job_id, step="stage_2_complete",
                             progress=0.66, message="Stage 2 done")
            real_dispatcher.emit(event2)
            job = Job.get_by_id(job_id)
            assert job.progress == 0.66, f"After stage 2: progress={job.progress}"
            assert job.current_stage == "evaluation"
            
            # Stage 3 transition
            event3 = JobEvent(job_id=job_id, step="stage_3_complete",
                             progress=0.99, message="Stage 3 done")
            real_dispatcher.emit(event3)
            job = Job.get_by_id(job_id)
            assert job.progress == 0.99, f"After stage 3: progress={job.progress}"
            assert job.current_stage == "evaluation"
    
    def test_event_persisted_to_database(self, peewee_test_db, app, real_dispatcher):
        """Events should be persisted to Event table."""
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # Emit event
            event = JobEvent(job_id=job_id, step="test_step", 
                            message="Test message", progress=0.5)
            real_dispatcher.emit(event)
            
            # Check Event table
            events = list(Event.select().where(Event.job_id == job_id))
            assert len(events) >= 1, "Event not persisted to database"
            
            test_events = [e for e in events if e.step == "test_step"]
            assert len(test_events) == 1
            assert test_events[0].message == "Test message"
    
    def test_non_stage_events_dont_update_job_stage(self, peewee_test_db, app, real_dispatcher):
        """Non-stage events should persist but not change job stage."""
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            original_stage = Job.get_by_id(job_id).current_stage
            
            # Emit non-stage event
            event = JobEvent(job_id=job_id, step="extracting_pdf",
                            message="Extracting...", progress=0.1)
            real_dispatcher.emit(event)
            
            # Job stage should NOT change (extracting_pdf is not a stage transition)
            job = Job.get_by_id(job_id)
            assert job.current_stage == original_stage, \
                f"Non-stage event changed stage: {original_stage} -> {job.current_stage}"
            # But progress might change if event has progress and it's handled elsewhere
            # (This test just verifies non-transition events don't trigger stage change)
    
    def test_chat_events_not_persisted(self, peewee_test_db, app, real_dispatcher):
        """Chat events should NOT be persisted (different handling)."""
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # Emit chat event (with content, no message)
            event = JobEvent(job_id=job_id, step="chat_response",
                            content="User asked...", progress=None)
            
            # Get event count before
            events_before = len(list(Event.select().where(Event.job_id == job_id)))
            
            real_dispatcher.emit(event)
            
            # Get event count after
            events_after = len(list(Event.select().where(Event.job_id == job_id)))
            
            # Chat events are NOT persisted (they're streaming)
            assert events_after == events_before, \
                "Chat event should not be persisted"
    
    def test_dispatcher_dependency_injection(self, peewee_test_db, app):
        """Verify dispatcher is properly configured with all dependencies.
        
        This would have caught the bug where dispatcher was created without job_service.
        """
        from blueprints.jobs import _dispatcher
        
        # After the fix, dispatcher should work end-to-end
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # This event should trigger a stage transition
            event = JobEvent(job_id=job_id, step="stage_1_complete",
                            progress=0.33)
            _dispatcher.emit(event)
            
            # If dispatcher is missing job_service, this assertion would fail
            job = Job.get_by_id(job_id)
            assert job.progress == 0.33, \
                "Dispatcher not properly configured - job progress not updated!"


class TestEventDispatcherRealVsMock:
    """Compare real dispatcher behavior vs mocked dispatcher.
    
    This documents why unit tests with mocks can miss integration bugs.
    """
    
    def test_real_dispatcher_updates_database(self, peewee_test_db, app):
        """Real dispatcher should update database."""
        from blueprints.jobs import _dispatcher
        
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            event = JobEvent(job_id=job_id, step="stage_1_complete", progress=0.33)
            _dispatcher.emit(event)
            
            job = Job.get_by_id(job_id)
            assert job.progress == 0.33
    
    def test_mock_dispatcher_doesnt_actually_update(self, peewee_test_db, app):
        """Mocked dispatcher won't catch missing dependencies.
        
        This test shows WHY unit tests with mocks are insufficient.
        """
        from unittest.mock import Mock
        from services.event_dispatcher import EventDispatcher
        
        with app.app_context():
            import uuid
            job_id = str(uuid.uuid4())
            create_job(job_id, "/path/to/pdf", "test.pdf", 1)
            
            # Create a MOCK dispatcher (like unit tests do)
            mock_dispatcher = Mock(spec=EventDispatcher)
            
            event = JobEvent(job_id=job_id, step="stage_1_complete", progress=0.33)
            mock_dispatcher.emit(event)
            
            # Mock was called, but database unchanged!
            job = Job.get_by_id(job_id)
            assert job.progress == 0.0  # ← Still 0.0! Mock didn't update DB
            
            # This is why unit tests missed the bug:
            # They only verified mock.emit() was called, not that DB was updated
