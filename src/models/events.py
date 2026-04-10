"""Event dataclasses for type-safe event handling."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class JobEvent:
    """Single job event."""

    job_id: str
    step: str
    message: Optional[str] = None
    severity: str = "info"
    progress: Optional[float] = None
    content: Optional[str] = None  # For streaming responses
    timestamp: Optional[str] = None
    stage_duration_ms: Optional[int] = None  # Duration in milliseconds

    def __post_init__(self):
        """Auto-set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "step": self.step,
            "message": self.message,
            "severity": self.severity,
            "progress": self.progress,
            "content": self.content,
            "timestamp": self.timestamp,
            "stage_duration_ms": self.stage_duration_ms,
        }

    def is_chat_event(self) -> bool:
        """Check if this is a chat-related event."""
        return self.step and self.step.startswith("chat_")

    def is_stage_transition(self) -> bool:
        """Check if this is a stage transition event."""
        stage_events = {
            "stage_1_starting",
            "stage_1_complete",
            "stage_2_starting",
            "stage_2_complete",
            "stage_3_starting",
            "stage_3_complete",
            "complete",
        }
        return self.step in stage_events


@dataclass
class StageTransition:
    """Stage transition metadata - defines which stage we're moving to."""

    from_stage: str
    to_stage: str
    event_step: str  # The event that triggered this transition
    progress: float = 0.0  # Progress value when this transition occurs


# Stage transition definitions (stage tracking only - progress comes from events)
STAGE_TRANSITIONS = {
    "stage_1_starting": StageTransition("pending", "paper_analysis", "stage_1_starting", 0.05),
    "stage_1_complete": StageTransition("paper_analysis", "code_execution", "stage_1_complete", 0.33),
    "stage_2_starting": StageTransition("code_execution", "code_execution", "stage_2_starting", 0.33),
    "stage_2_complete": StageTransition("code_execution", "evaluation", "stage_2_complete", 0.66),
    "stage_3_starting": StageTransition("evaluation", "evaluation", "stage_3_starting", 0.66),
    "stage_3_complete": StageTransition("evaluation", "evaluation", "stage_3_complete", 1.0),
    "complete": StageTransition("evaluation", "completed", "complete", 1.0),
}
