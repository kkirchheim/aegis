"""Event dispatcher - central hub for job events and stage transitions."""

import sys
from typing import Optional, Dict, List, Callable
from threading import Lock
from database import get_db
from models.events import JobEvent, STAGE_TRANSITIONS


class EventDispatcher:
    """Central event dispatcher for job pipeline events."""
    
    def __init__(
        self,
        event_queues: Dict = None,
        event_queues_lock: Lock = None,
        job_service = None,
        logger: Callable = None,
    ):
        """
        Initialize dispatcher with optional dependencies.
        
        Args:
            event_queues: Dict[job_id] -> List[events] for SSE streaming
            event_queues_lock: Thread lock for queue access
            job_service: Service for updating job status
            logger: Logging function (defaults to stderr)
        """
        self.event_queues = event_queues or {}
        self.event_queues_lock = event_queues_lock or Lock()
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
        3. Emit to SSE queues for real-time updates
        
        Args:
            event: JobEvent to emit
        """
        # Persist to database
        if not event.is_chat_event():
            self._persist_event(event)
        
        # Handle stage transitions
        if event.is_stage_transition():
            self._handle_stage_transition(event)
        
        # Emit to SSE clients
        self._emit_to_queues(event)
    
    def _persist_event(self, event: JobEvent) -> None:
        """Store event in database (non-chat events only)."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                INSERT INTO events (job_id, timestamp, step, message, severity)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event.job_id,
                event.timestamp,
                event.step,
                event.message or "",
                event.severity,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger(f"Failed to persist event: {e}")
    
    def _handle_stage_transition(self, event: JobEvent) -> None:
        """Update job status for stage transition events."""
        transition = STAGE_TRANSITIONS.get(event.step)
        
        if not transition:
            return
        
        # Log transition
        self.logger(
            f"[{event.job_id}] TRANSITION: {event.step} -> {transition.to_stage}"
        )
        
        # Update job status if service available
        if self.job_service:
            from services.job_service import update_job_status
            update_job_status(
                event.job_id,
                "processing" if transition.to_stage != "completed" else "completed",
                progress=transition.progress,
                current_stage=transition.to_stage,
            )
    
    def _emit_to_queues(self, event: JobEvent) -> None:
        """Emit event to SSE queues for real-time updates."""
        with self.event_queues_lock:
            if event.job_id in self.event_queues:
                self.event_queues[event.job_id].append(event.to_dict())


class EventDispatcherFactory:
    """Factory for creating dispatcher instances with proper dependencies."""
    
    @staticmethod
    def create(event_queues: Dict = None, event_queues_lock: Lock = None):
        """Create a dispatcher with all dependencies."""
        return EventDispatcher(
            event_queues=event_queues,
            event_queues_lock=event_queues_lock,
        )
    
    @staticmethod
    def create_test_dispatcher(
        event_queues: Dict = None,
        event_queues_lock: Lock = None,
        mock_logger: Callable = None,
    ):
        """Create a test dispatcher with mocked dependencies."""
        queues = event_queues or {}
        lock = event_queues_lock or Lock()
        logger = mock_logger or (lambda msg: None)  # Silent by default
        
        return EventDispatcher(
            event_queues=queues,
            event_queues_lock=lock,
            job_service=None,  # Mocked out for testing
            logger=logger,
        )
