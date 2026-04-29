"""
Marshmallow schemas for job management.

Provides serialization/deserialization schemas for:
- JobSchema: Individual job representation
- JobListSchema: List of jobs with metadata
- JobDetailSchema: Detailed job information including analysis and artifacts
- JobUploadSchema: File upload schema for job creation
"""

from marshmallow import Schema, fields, validate


class JobSchema(Schema):
    """
    Schema for serializing/deserializing individual job data.

    Represents the core job entity with status, progress, and metadata.
    Used for job listings and basic job information endpoints.
    """

    id = fields.Str(required=True, description="Unique job identifier")
    status = fields.Str(
        required=True,
        validate=validate.OneOf(["pending", "running", "completed", "failed", "cancelled"]),
        description="Current job status",
    )
    progress = fields.Float(
        allow_none=True, validate=validate.Range(min=0, max=100), description="Job progress percentage (0-100)"
    )
    current_stage = fields.Str(
        allow_none=True, description="Current processing stage (e.g., 'uploading', 'extracting', 'analyzing')"
    )
    created_at = fields.DateTime(allow_none=True, description="Timestamp when job was created")
    completed_at = fields.DateTime(allow_none=True, description="Timestamp when job was completed")
    pdf_filename = fields.Str(allow_none=True, description="Original PDF filename")
    thumbnail_path = fields.Str(allow_none=True, description="Path to PDF thumbnail image")
    user_id = fields.Int(allow_none=True, description="ID of the user who created the job")
    error_message = fields.Str(allow_none=True, description="Error message if job failed")

    class Meta:
        """Metadata configuration for JobSchema."""

        strict = True


class JobListSchema(Schema):
    """
    Schema for serializing a list of jobs with pagination metadata.

    Used for endpoints that return multiple jobs with count information.
    """

    jobs = fields.List(fields.Nested(JobSchema), allow_none=True, description="List of job objects")
    total = fields.Int(allow_none=True, description="Total number of jobs available")

    class Meta:
        """Metadata configuration for JobListSchema."""

        strict = True


class JobDetailSchema(Schema):
    """
    Schema for detailed job information including analysis results and artifacts.

    Extends JobSchema with additional fields for comprehensive job details,
    including processing events, paper analysis results, generated artifacts,
    and final reports.
    """

    # Core job fields (from JobSchema)
    id = fields.Str(required=True, description="Unique job identifier")
    status = fields.Str(
        required=True,
        validate=validate.OneOf(["pending", "running", "completed", "failed", "cancelled"]),
        description="Current job status",
    )
    progress = fields.Float(
        allow_none=True, validate=validate.Range(min=0, max=100), description="Job progress percentage (0-100)"
    )
    current_stage = fields.Str(allow_none=True, description="Current processing stage")
    created_at = fields.DateTime(allow_none=True, description="Timestamp when job was created")
    completed_at = fields.DateTime(allow_none=True, description="Timestamp when job was completed")
    pdf_filename = fields.Str(allow_none=True, description="Original PDF filename")
    thumbnail_path = fields.Str(allow_none=True, description="Path to PDF thumbnail image")
    user_id = fields.Int(allow_none=True, description="ID of the user who created the job")
    error_message = fields.Str(allow_none=True, description="Error message if job failed")

    # Extended detail fields
    events = fields.List(
        fields.Dict(), allow_none=True, description="List of processing events with timestamps and details"
    )
    paper_analysis = fields.Dict(
        allow_none=True, description="Extracted paper analysis including metadata, abstract, findings"
    )
    artifacts = fields.List(
        fields.Dict(), allow_none=True, description="Generated artifacts (images, tables, supplementary materials)"
    )
    report = fields.Dict(allow_none=True, description="Final reproducibility report and recommendations")
    evidence = fields.Dict(allow_none=True, description="Plugin evaluation evidence: {plugin_id: {status, reasoning}}")
    config = fields.Dict(allow_none=True, description="Job configuration at creation time")
    check_results = fields.List(
        fields.Dict(), allow_none=True, description="Execution check results with name, exit code, output, duration"
    )

    class Meta:
        """Metadata configuration for JobDetailSchema."""

        strict = True


class JobUploadSchema(Schema):
    """
    Schema for handling file uploads when creating a new job.

    Used for endpoints that accept PDF file uploads.
    The file field is marked as load_only since it's only used
    for deserialization (receiving uploads), not serialization (responses).
    """

    file = fields.Field(required=True, load_only=True, description="PDF file to process (multipart form upload)")

    class Meta:
        """Metadata configuration for JobUploadSchema."""

        strict = True
