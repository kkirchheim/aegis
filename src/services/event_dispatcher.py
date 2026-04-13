"""Event dispatcher - central hub for job events and stage transitions."""

import sys
from typing import Callable

from models.database import Event, Job
from models.events import STAGE_TRANSITIONS, JobEvent


class EventDispatcher:
    """Central event dispatcher for job pipeline events."""

    def __init__(
        self,
        job_service=None,
        logger: Callable = None,
    ):
        """
        Initialize dispatcher with optional dependencies.

        Args:
            job_service: Service for updating job status
            logger: Logging function (defaults to stderr)
        """
        self.job_service = job_service
        self.logger = logger or self._default_logger

    @staticmethod
    def _default_logger(msg: str):
        """Default logger writes to stderr."""
        print(msg, file=sys.stderr)

    def emit(self, event: JobEvent) -> None:
        """
        Emit a job event.

        Actions:
        1. Persist to database (unless chat event)
        2. Update job status for stage transitions
        3. Log ANY progress values (for debugging)

        Args:
            event: JobEvent to emit
        """
        # Persist to database
        if not event.is_chat_event():
            self._persist_event(event)

        # Handle stage transitions
        if event.is_stage_transition():
            self._handle_stage_transition(event)

        # Log ANY progress in event (even if not a stage transition)
        if event.progress is not None:
            self.logger(
                f"[{event.job_id}] *** EVENT INCLUDES PROGRESS: step={event.step}, progress={event.progress} ***"
            )

    def _persist_event(self, event: JobEvent) -> None:
        """Store event in database (non-chat events only)."""
        try:
            # Get job by ID
            try:
                job = Job.get_by_id(event.job_id)
            except Job.DoesNotExist:
                self.logger(f"[{event.job_id}] Job not found, cannot persist event: {event.step}")
                return

            # Create event using Peewee model
            Event.create(
                job=job,
                step=event.step,
                message=event.message or "",
                severity=event.severity,
                timestamp=event.timestamp,
                stage_duration_ms=event.stage_duration_ms,
            )
            self.logger(f"[{event.job_id}] Event persisted: {event.step}")
            if event.progress is not None:
                self.logger(f"[{event.job_id}] Event progress: {event.progress}")
        except Exception as e:
            self.logger(f"[{event.job_id}] Failed to persist event {event.step}: {type(e).__name__}: {e}")

    def _handle_stage_transition(self, event: JobEvent) -> None:
        """Update job status for stage transition events.

        Uses event.progress if provided (ground truth from pipeline).
        Only updates progress if event explicitly includes it.
        """
        transition = STAGE_TRANSITIONS.get(event.step)

        if not transition:
            return

        # Log transition
        self.logger(f"[{event.job_id}] TRANSITION: {event.step} -> {transition.to_stage}")

        # ALWAYS update job status for stage transitions
        # (this is the only place non-orchestrator code should update progress)
        from services.job_service import update_job_status

        # Build update dict
        updates = {
            "status": "processing" if transition.to_stage != "completed" else "completed",
            "current_stage": transition.to_stage,
        }

        # Use event.progress if provided (event is the ground truth)
        if event.progress is not None:
            updates["progress"] = event.progress
            self.logger(f"[{event.job_id}] *** DISPATCHER PASSING progress={event.progress} to update_job_status ***")
        else:
            self.logger(f"[{event.job_id}] *** DISPATCHER: No progress in event, NOT setting progress field ***")

        self.logger(f"[{event.job_id}] Calling update_job_status with: {updates}")
        update_job_status(event.job_id, **updates)


class EventDispatcherFactory:
    """Factory for creating dispatcher instances with proper dependencies."""

    @staticmethod
    def create():
        """Create a dispatcher with all dependencies."""
        return EventDispatcher()

    @staticmethod
    def create_test_dispatcher(
        mock_logger: Callable = None,
    ):
        """Create a test dispatcher with mocked dependencies."""
        logger = mock_logger or (lambda msg: None)  # Silent by default

        return EventDispatcher(
            job_service=None,  # Mocked out for testing
            logger=logger,
        )
