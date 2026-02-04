"""Event dataclasses for type-safe event handling."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


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
    
    def __post_init__(self):
        """Auto-set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'job_id': self.job_id,
            'step': self.step,
            'message': self.message,
            'severity': self.severity,
            'progress': self.progress,
            'content': self.content,
            'timestamp': self.timestamp,
        }
    
    def is_chat_event(self) -> bool:
        """Check if this is a chat-related event."""
        return self.step and self.step.startswith('chat_')
    
    def is_stage_transition(self) -> bool:
        """Check if this is a stage transition event."""
        stage_events = {
            'stage_1_starting', 'stage_1_complete',
            'stage_2_starting', 'stage_2_complete',
            'stage_3_starting', 'stage_3_complete',
            'complete'
        }
        return self.step in stage_events


@dataclass
class StageTransition:
    """Stage transition metadata."""
    from_stage: str
    to_stage: str
    progress: float
    event_step: str  # The event that triggered this transition


# Stage transition definitions
STAGE_TRANSITIONS = {
    'stage_1_starting': StageTransition('pending', 'paper_analysis', 0.05, 'stage_1_starting'),
    'stage_1_complete': StageTransition('paper_analysis', 'code_execution', 0.33, 'stage_1_complete'),
    'stage_2_starting': StageTransition('code_execution', 'code_execution', 0.34, 'stage_2_starting'),
    'stage_2_complete': StageTransition('code_execution', 'evaluation', 0.66, 'stage_2_complete'),
    'stage_3_starting': StageTransition('evaluation', 'evaluation', 0.67, 'stage_3_starting'),
    'stage_3_complete': StageTransition('evaluation', 'evaluation', 1.0, 'stage_3_complete'),
    'complete': StageTransition('evaluation', 'completed', 1.0, 'complete'),
}
