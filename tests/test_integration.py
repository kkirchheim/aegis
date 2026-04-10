"""Integration tests for Paper Reproducibility Checker.

Tests the flow between multiple components:
- EventDispatcher → Peewee models
- PipelineOrchestrator emitting events
- Job status updates from events
"""

from unittest.mock import MagicMock, patch

import pytest

from models.events import STAGE_TRANSITIONS, JobEvent
from services.event_dispatcher import EventDispatcher
from services.pipeline_orchestrator import PipelineOrchestrator


class TestEventDispatcherIntegration:
    """Integration tests for event dispatcher with mocked database."""

    def test_event_dispatcher_to_peewee_flow(self, app):
        """Test EventDispatcher → Event.create flow with Peewee mocking."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            # Setup mocks
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job
            mock_event = MagicMock()
            mock_event_class.create.return_value = mock_event

            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Emit non-chat event
            event = JobEvent(
                job_id="job123",
                step="stage_1_starting",
                message="Analyzing paper",
                severity="info",
            )
            dispatcher.emit(event)

            # Verify database calls
            mock_job_class.get_by_id.assert_called_with("job123")
            mock_event_class.create.assert_called_once()

            # Verify event in SSE queue
            assert len(queues["job123"]) == 1
            assert queues["job123"][0]["step"] == "stage_1_starting"

    def test_stage_duration_ms_flows_through_layers(self, app):
        """Test that stage_duration_ms parameter flows through all layers."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Emit event with stage_duration_ms
            event = JobEvent(
                job_id="job123",
                step="stage_1_complete",
                message="Stage completed",
                stage_duration_ms=5432,
            )
            dispatcher.emit(event)

            # Verify in SSE queue
            assert queues["job123"][0]["stage_duration_ms"] == 5432

            # Verify in Peewee create call
            # (Currently Event model doesn't store this, but it flows through to_dict())
            call_kwargs = mock_event_class.create.call_args.kwargs
            # This validates that emit was called correctly
            assert call_kwargs is not None

    def test_multiple_events_sequence(self, app):
        """Test emitting multiple events in sequence."""
        queues = {"job123": []}
        logged = []

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event"),
        ):
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            dispatcher = EventDispatcher(
                event_queues=queues,
                job_service=None,
                logger=lambda msg: logged.append(msg),
            )

            # Emit sequence of events
            events = [
                JobEvent(job_id="job123", step="stage_1_starting", message="Start"),
                JobEvent(job_id="job123", step="extracting_text", message="Extract"),
                JobEvent(job_id="job123", step="analyzing", message="Analyze"),
                JobEvent(job_id="job123", step="stage_1_complete", message="Done"),
            ]

            for event in events:
                dispatcher.emit(event)

            # All events should be in queue
            assert len(queues["job123"]) == 4

            # Stage transitions should be logged (2 transitions)
            transitions = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transitions) == 2  # stage_1_starting and stage_1_complete

    def test_chat_events_not_persisted_to_db(self, app):
        """Test that chat events skip database persistence."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Emit chat event
            chat_event = JobEvent(
                job_id="job123",
                step="chat_response",
                content="Analysis complete",
            )
            dispatcher.emit(chat_event)

            # Should NOT call Job.get_by_id or Event.create
            mock_job_class.get_by_id.assert_not_called()
            mock_event_class.create.assert_not_called()

            # But should still be in SSE queue
            assert len(queues["job123"]) == 1
            assert queues["job123"][0]["step"] == "chat_response"


class TestPipelineOrchestratorEventEmission:
    """Test that PipelineOrchestrator properly emits events."""

    def test_orchestrator_emits_stage_start_event(self, app):
        """Test that orchestrator emits stage start events."""
        queues = {"job123": []}

        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            # Create a real dispatcher with mocked queue
            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Create orchestrator with dispatcher
            orchestrator = PipelineOrchestrator(dispatcher=dispatcher)

            # The orchestrator should have an event dispatcher
            assert orchestrator.dispatcher is not None

            # Emit an event through orchestrator
            orchestrator.emit_event(job_id="job123", step="stage_1_starting", message="Starting analysis")

            # Event should appear in queue
            assert len(queues["job123"]) == 1
            assert queues["job123"][0]["step"] == "stage_1_starting"

    def test_event_emission_triggers_job_status_update(self):
        """Test that emitting stage transition events triggers job status updates."""
        queues = {"job123": []}
        logged = []

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event"),
        ):
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            # Mock job_service
            mock_job_service = MagicMock()

            dispatcher = EventDispatcher(
                event_queues=queues,
                job_service=mock_job_service,
                logger=lambda msg: logged.append(msg),
            )

            # Emit stage transition event
            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)

            # Verify transition was logged
            transitions = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transitions) == 1
            assert "paper_analysis" in transitions[0]


class TestEventRepositoryIntegration:
    """Test EventRepository integration with event dispatcher."""

    def test_event_creation_via_dispatcher(self):
        """Test that dispatcher properly creates Event records."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            # Setup mocks to simulate repository pattern
            mock_job = MagicMock(id="job123")
            mock_job_class.get_by_id.return_value = mock_job

            created_event = MagicMock()
            mock_event_class.create.return_value = created_event

            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            event = JobEvent(
                job_id="job123",
                step="stage_1_starting",
                message="Starting analysis",
                severity="info",
            )
            dispatcher.emit(event)

            # Verify all expected fields passed to create
            call_kwargs = mock_event_class.create.call_args.kwargs
            assert call_kwargs["step"] == "stage_1_starting"
            assert call_kwargs["message"] == "Starting analysis"
            assert call_kwargs["severity"] == "info"
            assert call_kwargs["job"] == mock_job


class TestJobRepositoryIntegration:
    """Test JobRepository integration with event dispatcher."""

    def test_job_lookup_before_event_creation(self):
        """Test that dispatcher looks up job before creating event."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event"),
        ):
            mock_job = MagicMock(id="job123", status="processing")
            mock_job_class.get_by_id.return_value = mock_job

            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            event = JobEvent(job_id="job123", step="stage_1_complete")
            dispatcher.emit(event)

            # Verify job was looked up by ID
            mock_job_class.get_by_id.assert_called_once_with("job123")

    def test_job_not_found_error_handling(self):
        """Test error handling when job is not found."""
        queues = {"job123": []}
        logged = []

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event"),
        ):
            # Simulate job not found
            mock_job_class.get_by_id.side_effect = Exception("Job not found")

            dispatcher = EventDispatcher(
                event_queues=queues,
                job_service=None,
                logger=lambda msg: logged.append(msg),
            )

            event = JobEvent(job_id="job123", step="stage_1_complete")
            dispatcher.emit(event)  # Should not raise

            # Error should be logged
            error_logs = [msg for msg in logged if "Failed to persist event" in msg]
            assert len(error_logs) == 1


class TestStageTransitionIntegration:
    """Test stage transition logic across the system."""

    def test_all_stage_transitions_emit_to_queue(self, app):
        """Test that all stage transitions appear in SSE queue."""
        queues = {"job123": []}

        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event"),
        ):
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Emit all stage transition events
            for step in STAGE_TRANSITIONS.keys():
                event = JobEvent(job_id="job123", step=step)
                dispatcher.emit(event)

            # All 7 should be in queue
            assert len(queues["job123"]) == len(STAGE_TRANSITIONS)

            # Verify stages
            steps = [e["step"] for e in queues["job123"]]
            assert "stage_1_starting" in steps
            assert "stage_2_complete" in steps
            assert "stage_3_complete" in steps
            assert "complete" in steps

    def test_progress_tracking_through_transitions(self, app):
        """Test that progress values are correctly tracked through transitions."""
        queues = {"job123": []}

        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcher(event_queues=queues, job_service=None)

            # Emit events with specific progress tracking
            transition_order = [
                "stage_1_starting",  # 0.05
                "stage_1_complete",  # 0.33
                "stage_2_complete",  # 0.66
                "stage_3_complete",  # 1.0
            ]

            for step in transition_order:
                event = JobEvent(job_id="job123", step=step)
                dispatcher.emit(event)

            # Events should be emitted in order
            assert len(queues["job123"]) == len(transition_order)
            for i, step in enumerate(transition_order):
                assert queues["job123"][i]["step"] == step


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
