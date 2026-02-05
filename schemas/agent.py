"""Marshmallow schemas for internal agent endpoints.

These schemas validate requests from the Docker agent container
for the orchestrator pipeline (think, log, execution, complete).
"""

from marshmallow import Schema, fields, validate


# ============================================================================
# INPUT VALIDATION SCHEMAS (for @use_kwargs)
# ============================================================================

class AgentThinkRequestSchema(Schema):
    """Schema for agent/think request validation.
    
    Agent calls this to ask the LLM what action to take next.
    """
    job_id = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        description="Job ID (UUID)"
    )
    repo_state = fields.Dict(
        required=False,
        allow_none=True,
        description="Current repository state (discovered_files, combined_output, executed_commands, errors, etc.)"
    )


class AgentLogRequestSchema(Schema):
    """Schema for agent/log request validation.
    
    Agent logs progress messages during code execution.
    """
    job_id = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        description="Job ID (UUID)"
    )
    message = fields.Str(
        required=False,
        allow_none=True,
        description="Progress message from agent"
    )


class AgentExecutionRequestSchema(Schema):
    """Schema for agent/execution request validation.
    
    Agent stores execution details after running code.
    """
    job_id = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        description="Job ID (UUID)"
    )
    commands_run = fields.Str(
        required=False,
        allow_none=True,
        description="Commands executed"
    )
    stdout_combined = fields.Str(
        required=False,
        allow_none=True,
        description="Combined stdout from all commands"
    )
    actual_results = fields.Dict(
        required=False,
        allow_none=True,
        description="Actual results from running code"
    )
    dependencies_used = fields.Str(
        required=False,
        allow_none=True,
        description="Dependencies/packages used"
    )
    errors_summary = fields.Str(
        required=False,
        allow_none=True,
        description="Summary of any errors encountered"
    )
    discovered_files = fields.List(
        fields.Str(),
        required=False,
        allow_none=True,
        description="Files discovered in repository"
    )
    test_info = fields.Str(
        required=False,
        allow_none=True,
        description="Information about tests"
    )
    randomness_info = fields.Str(
        required=False,
        allow_none=True,
        description="Information about randomness in execution"
    )


class AgentCompleteRequestSchema(Schema):
    """Schema for agent/complete request validation.
    
    Agent reports that analysis/execution is complete.
    """
    job_id = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        description="Job ID (UUID)"
    )
    success = fields.Bool(
        required=False,
        allow_none=True,
        description="Whether analysis was successful"
    )
    message = fields.Str(
        required=False,
        allow_none=True,
        description="Completion message"
    )


# ============================================================================
# OUTPUT RESPONSE SCHEMAS (for @marshal_with)
# ============================================================================

class AgentActionSchema(Schema):
    """Schema for agent/think response.
    
    LLM returns the next action for the agent to perform.
    """
    action = fields.Str(
        allow_none=True,
        description="Action type: read_file, run_command, check_success, done"
    )
    target = fields.Str(
        allow_none=True,
        description="Target file or command"
    )
    reasoning = fields.Str(
        allow_none=True,
        description="Reasoning for this action"
    )


class AgentResponseSchema(Schema):
    """Schema for agent endpoint success response.
    
    Used by agent/log, agent/execution, agent/complete.
    """
    ok = fields.Bool(
        allow_none=True,
        description="Whether request was successful"
    )
    message = fields.Str(
        allow_none=True,
        description="Response message"
    )
