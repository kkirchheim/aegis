"""
Marshmallow schemas for API documentation and validation.

This package contains all Marshmallow schemas used for API documentation
via flask-apispec. Each submodule organizes schemas by domain.

Schemas exported:
- Authentication: LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema
- Jobs: JobSchema, JobListSchema, JobDetailSchema, JobUploadSchema
- Chat: ChatMessageSchema, ChatMessageResponseSchema, ChatHistorySchema
- Results: ArtifactSchema, PluginEvaluationSchema, ExecutionResultSchema, PaperAnalysisSchema
- Admin: UserSchema, UserListSchema, UserActionSchema, UpdateUserStatusSchema
- Agent: AgentThinkRequestSchema, AgentLogRequestSchema, AgentExecutionRequestSchema, AgentCompleteRequestSchema, AgentActionSchema, AgentResponseSchema
- Common: ErrorSchema, PaginationSchema, SuccessMessageSchema
"""

from .admin import UpdateUserStatusSchema, UserActionSchema, UserListSchema, UserSchema
from .agent import (
    AgentActionSchema,
    AgentCompleteRequestSchema,
    AgentExecutionRequestSchema,
    AgentLogRequestSchema,
    AgentResponseSchema,
    AgentThinkRequestSchema,
)
from .api_key import APIKeyCreateSchema, APIKeyGenerateSchema, APIKeyListSchema, APIKeySchema
from .auth import ChangePasswordSchema, LoginSchema, RegisterSchema, SessionSchema
from .chat import ChatHistorySchema, ChatMessageRequestSchema, ChatMessageResponseSchema, ChatMessageSchema
from .common import (
    CacheStatsResponseSchema,
    ErrorSchema,
    EventSchema,
    HealthResponseSchema,
    PaginationSchema,
    SuccessMessageSchema,
    UploadJobResponseSchema,
)
from .jobs import JobDetailSchema, JobListSchema, JobSchema, JobUploadSchema
from .results import ArtifactSchema, ExecutionResultSchema, PaperAnalysisSchema, PluginEvaluationSchema

__all__ = [
    # Common
    "ErrorSchema",
    "PaginationSchema",
    "SuccessMessageSchema",
    "EventSchema",
    "HealthResponseSchema",
    "CacheStatsResponseSchema",
    "UploadJobResponseSchema",
    # Auth (Response & Input)
    "LoginSchema",
    "RegisterSchema",
    "ChangePasswordSchema",
    "SessionSchema",
    # Jobs
    "JobSchema",
    "JobListSchema",
    "JobDetailSchema",
    "JobUploadSchema",
    # Chat (Response & Input)
    "ChatMessageSchema",
    "ChatMessageResponseSchema",
    "ChatHistorySchema",
    "ChatMessageRequestSchema",
    # Results
    "ArtifactSchema",
    "PluginEvaluationSchema",
    "ExecutionResultSchema",
    "PaperAnalysisSchema",
    # Admin (Response & Input)
    "UserSchema",
    "UserListSchema",
    "UserActionSchema",
    "UpdateUserStatusSchema",
    # Agent (Internal - Response & Input)
    "AgentThinkRequestSchema",
    "AgentLogRequestSchema",
    "AgentExecutionRequestSchema",
    "AgentCompleteRequestSchema",
    "AgentActionSchema",
    "AgentResponseSchema",
    # API Keys (External Auth)
    "APIKeyCreateSchema",
    "APIKeySchema",
    "APIKeyGenerateSchema",
    "APIKeyListSchema",
]
