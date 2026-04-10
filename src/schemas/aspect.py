"""Aspect management schemas for API requests and responses.

This module contains Marshmallow schemas for validating aspect-related
requests and responses, including aspect creation, updates, activation,
and prompt overrides.
"""

from marshmallow import Schema, fields, validate


class AspectCreateSchema(Schema):
    """Schema for creating a new custom aspect.

    Attributes:
        name (str): Aspect name (required, 1-255 chars)
        description (str): Aspect description (required)
        prompt (str): Evaluation prompt template (required)
    """

    name = fields.Str(
        required=True, validate=validate.Length(min=1, max=255), description="Aspect name (1-255 characters)"
    )
    description = fields.Str(required=True, description="Aspect description")
    prompt = fields.Str(required=True, description="Evaluation prompt template")


class AspectUpdateSchema(Schema):
    """Schema for updating a custom aspect.

    All fields are optional - at least one must be provided.

    Attributes:
        name (str): Updated aspect name (optional, 1-255 chars)
        description (str): Updated aspect description (optional)
        prompt (str): Updated evaluation prompt (optional)
    """

    name = fields.Str(
        required=False,
        allow_none=False,
        validate=validate.Length(min=1, max=255),
        description="Updated aspect name (1-255 characters)",
    )
    description = fields.Str(required=False, allow_none=False, description="Updated aspect description")
    prompt = fields.Str(required=False, allow_none=False, description="Updated evaluation prompt template")


class ActivateAspectSchema(Schema):
    """Schema for toggling aspect activation status.

    Attributes:
        is_active (bool): Whether aspect should be active (required)
    """

    is_active = fields.Bool(required=True, description="Whether aspect should be active")


class OverridePromptSchema(Schema):
    """Schema for overriding aspect prompt.

    Attributes:
        custom_prompt (str): Custom prompt override (optional, nullable)
                            Pass None/null to revert to default prompt
    """

    custom_prompt = fields.Str(
        required=False, allow_none=True, description="Custom prompt override (null to revert to default)"
    )


# Output schemas for responses
class AspectSchema(Schema):
    """Schema for basic aspect information (global template).

    Used when returning information about an aspect definition.
    """

    id = fields.UUID(description="Unique aspect identifier")
    name = fields.Str(description="Aspect name")
    description = fields.Str(description="Aspect description")
    prompt = fields.Str(description="Default evaluation prompt template")
    is_default = fields.Bool(description="Whether this is a default system aspect")
    created_at = fields.DateTime(description="When aspect was created")
    updated_at = fields.DateTime(description="When aspect was last updated")


class UserAspectSchema(Schema):
    """Schema for user-aspect relationship with all settings.

    Represents a user's version of an aspect including their
    activation status and any prompt customizations.
    """

    id = fields.UUID(description="Unique user-aspect identifier")
    aspect_id = fields.UUID(description="Reference to the global aspect")
    name = fields.Str(description="Aspect name")
    description = fields.Str(description="Aspect description")
    is_default = fields.Bool(description="Whether this is a default system aspect")
    is_active = fields.Bool(description="Whether this aspect is active for the user")
    custom_prompt = fields.Str(allow_none=True, description="Custom prompt override (null if using default)")
    prompt_to_use = fields.Str(description="The actual prompt to use (custom or default)")
    created_at = fields.DateTime(description="When user activated this aspect")


class AspectListSchema(Schema):
    """Schema for listing aspects with pagination info.

    Attributes:
        aspects (list): List of UserAspectSchema items
        total (int): Total count of aspects for user
    """

    aspects = fields.List(fields.Nested(UserAspectSchema), description="List of user aspects")
    total = fields.Int(description="Total number of aspects for user")
