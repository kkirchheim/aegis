"""Tests for event dispatcher and event models."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from models.events import STAGE_TRANSITIONS, JobEvent
from services.event_dispatcher import EventDispatcher, EventDispatcherFactory


class TestJobEvent:
    """Test JobEvent dataclass."""

    def test_event_creation(self):
        """Test creating a JobEvent."""
        event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
            message="Starting analysis",
            severity="info",
        )
        assert event.job_id == "job123"
        assert event.step == "stage_1_starting"
        assert event.message == "Starting analysis"
        assert event.timestamp is not None

    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = JobEvent(
            job_id="job123",
            step="stage_1_complete",
            message="Done",
            severity="info",
            progress=0.33,
        )
        d = event.to_dict()
        assert d["job_id"] == "job123"
        assert d["step"] == "stage_1_complete"
        assert d["progress"] == 0.33
        assert "timestamp" in d

    def test_event_with_stage_duration(self):
        """Test that JobEvent accepts and serializes stage_duration_ms."""
        event = JobEvent(
            job_id="job123",
            step="stage_1_complete",
            message="Done",
            stage_duration_ms=1234,
        )
        assert event.stage_duration_ms == 1234

        d = event.to_dict()
        assert d["stage_duration_ms"] == 1234

    def test_chat_event_detection(self):
        """Test detecting chat events."""
        chat_event = JobEvent(
            job_id="job123",
            step="chat_response",
            content="Hello",
        )
        assert chat_event.is_chat_event() is True

        regular_event = JobEvent(
            job_id="job123",
            step="stage_1_starting",
        )
        assert regular_event.is_chat_event() is False

    def test_stage_transition_detection(self):
        """Test detecting stage transition events."""
        transition_events = [
            "stage_1_starting",
            "stage_1_complete",
            "stage_2_starting",
            "stage_2_complete",
            "stage_3_starting",
            "stage_3_complete",
            "complete",
        ]

        for step in transition_events:
            event = JobEvent(job_id="job123", step=step)
            assert event.is_stage_transition() is True, f"Failed for step: {step}"

        non_transition = JobEvent(job_id="job123", step="extracting_pdf")
        assert non_transition.is_stage_transition() is False


class TestStageTransitions:
    """Test stage transition metadata."""

    def test_all_transitions_defined(self):
        """Test that all expected transitions are defined."""
        expected = {
            "stage_1_starting",
            "stage_1_complete",
            "stage_2_starting",
            "stage_2_complete",
            "stage_3_starting",
            "stage_3_complete",
            "complete",
        }
        assert set(STAGE_TRANSITIONS.keys()) == expected

    def test_transition_properties(self, app):
        """Test transition metadata."""
        t = STAGE_TRANSITIONS["stage_1_starting"]
        assert t.from_stage == "pending"
        assert t.to_stage == "paper_analysis"
        assert t.progress == 0.05
        assert t.event_step == "stage_1_starting"

    def test_stage_3_complete_stays_in_evaluation(self, app):
        """Test that stage_3_complete doesn't transition to completed."""
        t = STAGE_TRANSITIONS["stage_3_complete"]
        assert t.from_stage == "evaluation"
        assert t.to_stage == "evaluation"  # Stays in evaluation
        assert t.progress == 1.0

    def test_complete_transitions_to_completed(self):
        """Test that complete event transitions to completed stage."""
        t = STAGE_TRANSITIONS["complete"]
        assert t.from_stage == "evaluation"
        assert t.to_stage == "completed"


class TestEventDispatcher:
    """Test EventDispatcher functionality."""

    def test_dispatcher_creation(self):
        """Test creating a dispatcher."""
        queues = {"job123": []}
        lock = threading.Lock()
        dispatcher = EventDispatcher(event_queues=queues, event_queues_lock=lock)

        assert dispatcher.event_queues == queues
        assert dispatcher.event_queues_lock is lock

    def test_emit_non_chat_event_to_queue(self, app):
        """Test emitting non-chat event to SSE queue."""
        queues = {"job123": []}
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)

        event = JobEvent(job_id="job123", step="stage_1_starting")
        dispatcher.emit(event)

        assert len(queues["job123"]) == 1
        assert queues["job123"][0]["step"] == "stage_1_starting"

    def test_emit_chat_event_to_queue(self, app):
        """Test emitting chat event to SSE queue."""
        queues = {"job123": []}
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)

        event = JobEvent(job_id="job123", step="chat_response", content="Hello")
        dispatcher.emit(event)

        # Chat event still emitted to queue (for streaming)
        assert len(queues["job123"]) == 1
        assert queues["job123"][0]["step"] == "chat_response"

    def test_emit_to_nonexistent_queue(self):
        """Test emitting to job with no queue (no error)."""
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues={})

        event = JobEvent(job_id="job123", step="stage_1_starting")
        # Should not raise error
        dispatcher.emit(event)

    def test_emit_event_with_stage_duration(self, app):
        """Test that emit_event properly passes stage_duration_ms to JobEvent."""
        queues = {"job123": []}
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)

        event = JobEvent(
            job_id="job123",
            step="stage_1_complete",
            message="Done",
            stage_duration_ms=5000,
        )
        dispatcher.emit(event)

        # Check that the event in the queue has stage_duration_ms
        assert len(queues["job123"]) == 1
        queued_event = queues["job123"][0]
        assert queued_event["stage_duration_ms"] == 5000
        assert queued_event["step"] == "stage_1_complete"

    def test_persist_non_chat_event(self):
        """Test that non-chat events are persisted using Peewee models."""
        queues = {"job123": []}

        # Mock Peewee models
        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            # Setup mock Job
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            # Setup mock Event.create
            mock_event = MagicMock()
            mock_event_class.create.return_value = mock_event

            dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)
            event = JobEvent(job_id="job123", step="stage_1_starting", message="Starting")
            dispatcher.emit(event)

            # Should call Job.get_by_id
            mock_job_class.get_by_id.assert_called_once_with("job123")

            # Should call Event.create with correct arguments
            mock_event_class.create.assert_called_once()
            call_kwargs = mock_event_class.create.call_args.kwargs
            assert call_kwargs["step"] == "stage_1_starting"
            assert call_kwargs["message"] == "Starting"

    def test_no_persist_chat_event(self):
        """Test that chat events are NOT persisted to database using Peewee models."""
        queues = {"job123": []}

        # Mock Peewee models
        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)
            event = JobEvent(job_id="job123", step="chat_response", content="Hello")
            dispatcher.emit(event)

            # Chat events should NOT persist, so Job.get_by_id and Event.create should NOT be called
            mock_job_class.get_by_id.assert_not_called()
            mock_event_class.create.assert_not_called()

    def test_stage_transition_logging(self):
        """Test that stage transitions are logged."""
        queues = {"job123": []}
        logged_messages = []

        def mock_logger(msg):
            logged_messages.append(msg)

        # Mock Peewee models
        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcher(
                event_queues=queues,
                event_queues_lock=threading.Lock(),
                logger=mock_logger,
                job_service=None,  # Skip job_service for this test
            )

            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)

            # Should have 1 transition log message
            transition_logs = [msg for msg in logged_messages if "TRANSITION" in msg]
            assert len(transition_logs) == 1
            assert "paper_analysis" in transition_logs[0]

    def test_all_stage_transitions(self):
        """Test that all stage transitions are handled correctly."""
        queues = {"job123": []}
        logged = []

        # Mock Peewee models
        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcher(
                event_queues=queues,
                event_queues_lock=threading.Lock(),
                logger=lambda msg: logged.append(msg),
                job_service=None,  # Skip job_service for this test
            )

            for step in STAGE_TRANSITIONS.keys():
                event = JobEvent(job_id="job123", step=step)
                dispatcher.emit(event)

            # Should log 7 transitions
            transition_logs = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transition_logs) == len(STAGE_TRANSITIONS)

            # Check specific transitions
            assert any("paper_analysis" in msg for msg in transition_logs)
            assert any("code_execution" in msg for msg in transition_logs)
            assert any("evaluation" in msg for msg in transition_logs)
            assert any("completed" in msg for msg in transition_logs)


class TestEventDispatcherFactory:
    """Test EventDispatcher factory."""

    def test_create_default_dispatcher(self):
        """Test creating a dispatcher with defaults."""
        dispatcher = EventDispatcherFactory.create()
        assert dispatcher is not None
        assert dispatcher.event_queues == {}
        assert dispatcher.event_queues_lock is not None

    def test_create_test_dispatcher(self):
        """Test creating a test dispatcher."""
        dispatcher = EventDispatcherFactory.create_test_dispatcher()
        assert dispatcher is not None
        # Test dispatcher should not log by default
        # (mock logger is silent)

    def test_test_dispatcher_silent_logging(self):
        """Test that test dispatcher uses provided logger."""
        logged = []

        def test_logger(msg):
            logged.append(msg)

        # Mock Peewee models
        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcherFactory.create_test_dispatcher(mock_logger=test_logger)

            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)

            # Should log 1 transition message
            transition_logs = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transition_logs) == 1


class TestEventDispatcherThreadSafety:
    """Test thread safety of event dispatcher."""

    def test_concurrent_emits(self, app):
        """Test emitting events concurrently."""
        queues = {"job123": []}
        dispatcher = EventDispatcherFactory.create_test_dispatcher(event_queues=queues)

        def emit_events(job_id, count):
            for i in range(count):
                event = JobEvent(job_id=job_id, step=f"step_{i}")
                dispatcher.emit(event)

        threads = [
            threading.Thread(target=emit_events, args=("job123", 10)),
            threading.Thread(target=emit_events, args=("job123", 10)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have exactly 20 events
        assert len(queues["job123"]) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
