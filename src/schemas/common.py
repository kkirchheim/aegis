"""
Common Marshmallow schemas for API requests and responses.

This module contains reusable schemas for:
- Input validation (requests)
- Output serialization (responses)
- Error responses, pagination metadata, and success messages
"""

from marshmallow import Schema, fields, validate


class ErrorSchema(Schema):
    """
    Schema for error responses.

    Attributes:
        error (str): Error type or code (optional).
        message (str): Detailed error message (optional).
        status_code (int): HTTP status code (optional).
    """

    error = fields.Str(required=False, allow_none=True)
    message = fields.Str(required=False, allow_none=True)
    status_code = fields.Int(required=False, allow_none=True)


class PaginationSchema(Schema):
    """
    Schema for pagination metadata in API responses.

    Attributes:
        page (int): Current page number (optional).
        per_page (int): Number of items per page (optional).
        total (int): Total number of items (optional).
        pages (int): Total number of pages (optional).
    """

    page = fields.Int(required=False, allow_none=True)
    per_page = fields.Int(required=False, allow_none=True)
    total = fields.Int(required=False, allow_none=True)
    pages = fields.Int(required=False, allow_none=True)


class SuccessMessageSchema(Schema):
    """
    Schema for success message responses.

    Attributes:
        ok (bool): Success indicator (required). Must be True to indicate success.
        message (str): Optional message describing the result (optional).
    """

    ok = fields.Bool(required=True)
    message = fields.Str(required=False, allow_none=True)


class EventSchema(Schema):
    """
    Schema for job processing events.

    Represents individual events that occur during job processing,
    including step name, timestamp, progress, and event-specific content.

    Attributes:
        step (str): Event step/type identifier (e.g., 'uploading', 'analyzing')
        timestamp (datetime): When the event occurred
        progress (float): Current progress percentage if applicable
        message (str): Event message or description
        content (str): Event content/details
        data (dict): Additional event-specific data
    """

    step = fields.Str(allow_none=True, description="Event step type")
    timestamp = fields.DateTime(allow_none=True, description="When the event occurred")
    progress = fields.Float(allow_none=True, description="Progress percentage (0-100)")
    message = fields.Str(allow_none=True, description="Event message")
    content = fields.Str(allow_none=True, description="Event content")
    data = fields.Dict(allow_none=True, description="Additional event data")


class HealthResponseSchema(Schema):
    """
    Schema for health check responses.

    Used by the health check endpoint to report system status.

    Attributes:
        status (str): Overall health status ('healthy' or 'unhealthy')
        timestamp (str): ISO format timestamp of the check
        checks (dict): Optional detailed health checks (development only)
    """

    status = fields.Str(
        required=True, validate=validate.OneOf(["healthy", "unhealthy"]), description="Overall health status"
    )
    timestamp = fields.Str(required=True, description="ISO format timestamp of health check")
    checks = fields.Dict(allow_none=True, description="Detailed health checks (database, docker, llm_provider)")


class CacheStatsResponseSchema(Schema):
    """
    Schema for cache statistics response.

    Reports current cache usage and statistics.

    Attributes:
        total_files (int): Total number of cached files
        total_size_mb (float): Total cache size in megabytes
        oldest_file (str): Path to oldest cached file
        newest_file (str): Path to newest cached file
        cache_dir (str): Cache directory path
    """

    total_files = fields.Int(allow_none=True, description="Total cached files")
    total_size_mb = fields.Float(allow_none=True, description="Total cache size in MB")
    oldest_file = fields.Str(allow_none=True, description="Oldest cached file")
    newest_file = fields.Str(allow_none=True, description="Newest cached file")
    cache_dir = fields.Str(allow_none=True, description="Cache directory path")


class UploadJobResponseSchema(Schema):
    """
    Schema for job upload response.

    Returned when a PDF is successfully uploaded for analysis.

    Attributes:
        job_id (str): Unique identifier for the created job
        status (str): Initial job status ('pending')
        message (str): Status message
    """

    job_id = fields.Str(required=True, description="Unique job identifier")
    status = fields.Str(allow_none=True, description="Job status")
    message = fields.Str(allow_none=True, description="Status message")


# ============================================================================
# INPUT VALIDATION SCHEMAS (for @use_kwargs)
# ============================================================================
# Note: Input schemas are defined in their respective modules:
# - auth.py: LoginSchema, RegisterSchema, ChangePasswordSchema
# - admin.py: UpdateUserStatusSchema (to be added)
# - chat.py: ChatMessageSchema (to be added)
#
# They are imported and re-exported in __init__.py for centralized access
