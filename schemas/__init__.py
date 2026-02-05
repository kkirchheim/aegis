"""
Marshmallow schemas for API documentation and validation.

This package contains all Marshmallow schemas used for API documentation
via flask-apispec. Each submodule organizes schemas by domain.

Schemas exported:
- Authentication: LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema
- Jobs: JobSchema, JobListSchema, JobDetailSchema, JobUploadSchema
- Chat: ChatMessageSchema, ChatMessageResponseSchema, ChatHistorySchema
- Results: ArtifactSchema, AspectEvaluationSchema, ExecutionResultSchema, PaperAnalysisSchema
- Admin: UserSchema, UserListSchema, UserActionSchema, UpdateUserStatusSchema
- Agent: AgentThinkRequestSchema, AgentLogRequestSchema, AgentExecutionRequestSchema, AgentCompleteRequestSchema, AgentActionSchema, AgentResponseSchema
- Common: ErrorSchema, PaginationSchema, SuccessMessageSchema
"""

from .common import (
    ErrorSchema, PaginationSchema, SuccessMessageSchema,
    EventSchema, HealthResponseSchema, CacheStatsResponseSchema, UploadJobResponseSchema
)
from .auth import LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema
from .jobs import JobSchema, JobListSchema, JobDetailSchema, JobUploadSchema
from .chat import ChatMessageSchema, ChatMessageResponseSchema, ChatHistorySchema, ChatMessageRequestSchema
from .results import ArtifactSchema, AspectEvaluationSchema, ExecutionResultSchema, PaperAnalysisSchema
from .admin import UserSchema, UserListSchema, UserActionSchema, UpdateUserStatusSchema
from .agent import (
    AgentThinkRequestSchema, AgentLogRequestSchema, AgentExecutionRequestSchema,
    AgentCompleteRequestSchema, AgentActionSchema, AgentResponseSchema
)

__all__ = [
    # Common
    'ErrorSchema',
    'PaginationSchema',
    'SuccessMessageSchema',
    'EventSchema',
    'HealthResponseSchema',
    'CacheStatsResponseSchema',
    'UploadJobResponseSchema',
    # Auth (Response & Input)
    'LoginSchema',
    'RegisterSchema',
    'ChangePasswordSchema',
    'SessionSchema',
    # Jobs
    'JobSchema',
    'JobListSchema',
    'JobDetailSchema',
    'JobUploadSchema',
    # Chat (Response & Input)
    'ChatMessageSchema',
    'ChatMessageResponseSchema',
    'ChatHistorySchema',
    'ChatMessageRequestSchema',
    # Results
    'ArtifactSchema',
    'AspectEvaluationSchema',
    'ExecutionResultSchema',
    'PaperAnalysisSchema',
    # Admin (Response & Input)
    'UserSchema',
    'UserListSchema',
    'UserActionSchema',
    'UpdateUserStatusSchema',
    # Agent (Internal - Response & Input)
    'AgentThinkRequestSchema',
    'AgentLogRequestSchema',
    'AgentExecutionRequestSchema',
    'AgentCompleteRequestSchema',
    'AgentActionSchema',
    'AgentResponseSchema',
]
