"""Tests for event dispatcher and event models."""

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
        dispatcher = EventDispatcher()
        assert dispatcher is not None

    def test_emit_non_chat_event(self, app):
        """Test emitting non-chat event."""
        dispatcher = EventDispatcherFactory.create_test_dispatcher()

        event = JobEvent(job_id="job123", step="stage_1_starting")
        dispatcher.emit(event)

    def test_emit_chat_event_not_persisted(self):
        """Test that chat events are NOT persisted to database."""
        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            dispatcher = EventDispatcherFactory.create_test_dispatcher()
            event = JobEvent(job_id="job123", step="chat_response", content="Hello")
            dispatcher.emit(event)

            # Chat events should NOT persist
            mock_job_class.get_by_id.assert_not_called()
            mock_event_class.create.assert_not_called()

    def test_persist_non_chat_event(self):
        """Test that non-chat events are persisted using Peewee models."""
        with (
            patch("services.event_dispatcher.Job") as mock_job_class,
            patch("services.event_dispatcher.Event") as mock_event_class,
        ):
            mock_job = MagicMock()
            mock_job_class.get_by_id.return_value = mock_job

            mock_event = MagicMock()
            mock_event_class.create.return_value = mock_event

            dispatcher = EventDispatcherFactory.create_test_dispatcher()
            event = JobEvent(job_id="job123", step="stage_1_starting", message="Starting")
            dispatcher.emit(event)

            mock_job_class.get_by_id.assert_called_once_with("job123")

            mock_event_class.create.assert_called_once()
            call_kwargs = mock_event_class.create.call_args.kwargs
            assert call_kwargs["step"] == "stage_1_starting"
            assert call_kwargs["message"] == "Starting"

    def test_stage_transition_logging(self):
        """Test that stage transitions are logged."""
        logged_messages = []

        def mock_logger(msg):
            logged_messages.append(msg)

        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcher(
                logger=mock_logger,
                job_service=None,
            )

            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)

            transition_logs = [msg for msg in logged_messages if "TRANSITION" in msg]
            assert len(transition_logs) == 1
            assert "paper_analysis" in transition_logs[0]

    def test_all_stage_transitions(self):
        """Test that all stage transitions are handled correctly."""
        logged = []

        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcher(
                logger=lambda msg: logged.append(msg),
                job_service=None,
            )

            for step in STAGE_TRANSITIONS.keys():
                event = JobEvent(job_id="job123", step=step)
                dispatcher.emit(event)

            transition_logs = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transition_logs) == len(STAGE_TRANSITIONS)

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

    def test_create_test_dispatcher(self):
        """Test creating a test dispatcher."""
        dispatcher = EventDispatcherFactory.create_test_dispatcher()
        assert dispatcher is not None

    def test_test_dispatcher_custom_logging(self):
        """Test that test dispatcher uses provided logger."""
        logged = []

        def test_logger(msg):
            logged.append(msg)

        with patch("services.event_dispatcher.Job"), patch("services.event_dispatcher.Event"):
            dispatcher = EventDispatcherFactory.create_test_dispatcher(mock_logger=test_logger)

            event = JobEvent(job_id="job123", step="stage_1_starting")
            dispatcher.emit(event)

            transition_logs = [msg for msg in logged if "TRANSITION" in msg]
            assert len(transition_logs) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
