"""
Chat-related Marshmallow schemas for request/response validation.

This module provides schemas for chat message handling, including
message submission, response formatting, and conversation history.
"""

from marshmallow import Schema, fields, validate


class ChatMessageSchema(Schema):
    """
    Schema for validating chat message submissions.

    Attributes:
        message (str): The chat message content.
        job_id (str): The associated job identifier.
    """

    message = fields.Str(required=True)
    job_id = fields.Str(required=True)


class ChatMessageResponseSchema(Schema):
    """
    Schema for formatting chat message responses.

    Attributes:
        role (str): The role of the message sender (e.g., 'user', 'assistant').
        content (str): The message content.
        timestamp (datetime): The timestamp of when the message was created.
    """

    role = fields.Str(allow_none=True, description="Message sender role (user or assistant)")
    content = fields.Str(allow_none=True, description="Message content")
    timestamp = fields.DateTime(allow_none=True, description="When the message was created")


class ChatHistorySchema(Schema):
    """
    Schema for chat conversation history.

    Attributes:
        messages (list): A list of ChatMessageResponseSchema messages.
        total (int): The total number of messages in the history.
    """

    messages = fields.List(
        fields.Nested(ChatMessageResponseSchema), allow_none=True, description="List of chat messages"
    )
    total = fields.Int(allow_none=True, description="Total number of messages in the history")


# ============================================================================
# INPUT VALIDATION SCHEMAS
# ============================================================================


class ChatMessageRequestSchema(Schema):
    """
    Schema for validating incoming chat messages.

    Attributes:
        message (str): Chat message content (1-5000 chars, required)
    """

    message = fields.Str(
        required=True, validate=validate.Length(min=1, max=5000), description="Chat message (1-5000 characters)"
    )
