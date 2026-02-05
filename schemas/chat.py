"""
Chat-related Marshmallow schemas for request/response validation.

This module provides schemas for chat message handling, including
message submission, response formatting, and conversation history.
"""

from marshmallow import Schema, fields


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
    role = fields.Str()
    content = fields.Str()
    timestamp = fields.DateTime()


class ChatHistorySchema(Schema):
    """
    Schema for chat conversation history.
    
    Attributes:
        messages (list): A list of ChatMessageResponseSchema messages.
        total (int): The total number of messages in the history.
    """
    messages = fields.List(fields.Nested(ChatMessageResponseSchema))
    total = fields.Int()
