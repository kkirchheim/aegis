"""Plugin management schemas for API requests and responses."""

from marshmallow import Schema, fields, validate


class PluginCreateSchema(Schema):
    """Schema for creating a new custom plugin."""

    name = fields.Str(
        required=True, validate=validate.Length(min=1, max=255), description="Plugin name (1-255 characters)"
    )
    description = fields.Str(required=True, description="Plugin description")
    prompt = fields.Str(required=True, description="Evaluation prompt template")


class PluginUpdateSchema(Schema):
    """Schema for updating a custom plugin."""

    name = fields.Str(
        required=False,
        allow_none=False,
        validate=validate.Length(min=1, max=255),
        description="Updated plugin name (1-255 characters)",
    )
    description = fields.Str(required=False, allow_none=False, description="Updated plugin description")
    prompt = fields.Str(required=False, allow_none=False, description="Updated evaluation prompt template")


class ActivatePluginSchema(Schema):
    """Schema for toggling plugin activation status."""

    is_active = fields.Bool(required=True, description="Whether plugin should be active")


class OverridePromptSchema(Schema):
    """Schema for overriding plugin prompt."""

    custom_prompt = fields.Str(
        required=False, allow_none=True, description="Custom prompt override (null to revert to default)"
    )


# Output schemas for responses
class PluginSchema(Schema):
    """Schema for basic plugin information (global template)."""

    id = fields.UUID(description="Unique plugin identifier")
    name = fields.Str(description="Plugin name")
    description = fields.Str(description="Plugin description")
    prompt = fields.Str(description="Default evaluation prompt template")
    is_default = fields.Bool(description="Whether this is a default system plugin")
    created_at = fields.DateTime(description="When plugin was created")
    updated_at = fields.DateTime(description="When plugin was last updated")


class UserPluginSchema(Schema):
    """Schema for user-plugin relationship with all settings."""

    id = fields.UUID(description="Unique user-plugin identifier")
    plugin_id = fields.UUID(description="Reference to the global plugin")
    name = fields.Str(description="Plugin name")
    description = fields.Str(description="Plugin description")
    is_default = fields.Bool(description="Whether this is a default system plugin")
    is_active = fields.Bool(description="Whether this plugin is active for the user")
    custom_prompt = fields.Str(allow_none=True, description="Custom prompt override (null if using default)")
    prompt_to_use = fields.Str(description="The actual prompt to use (custom or default)")
    created_at = fields.DateTime(description="When user activated this plugin")


class PluginListSchema(Schema):
    """Schema for listing plugins with pagination info."""

    plugins = fields.List(fields.Nested(UserPluginSchema), description="List of user plugins")
    total = fields.Int(description="Total number of plugins for user")
