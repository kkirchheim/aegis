"""Marshmallow schemas for API key management endpoints."""

from marshmallow import Schema, fields, validate


# ============================================================================
# INPUT VALIDATION SCHEMAS (for @use_kwargs)
# ============================================================================

class APIKeyCreateSchema(Schema):
    """Schema for creating a new API key.
    
    Attributes:
        name (str): Human-readable name for this key
    """
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        description="Name for this API key (e.g., 'CLI Tool', 'Integration Service')"
    )


# ============================================================================
# OUTPUT RESPONSE SCHEMAS (for @marshal_with)
# ============================================================================

class APIKeySchema(Schema):
    """Schema for API key in list/response (prefix only, never full key).
    
    Attributes:
        id (str): Unique API key identifier
        name (str): Human-readable name
        key_prefix (str): First 8 characters of key (safe to display)
        created_at (datetime): When this key was created
        last_used_at (datetime): When this key was last used
        is_active (bool): Whether this key is currently active
    """
    id = fields.Str(
        description="Unique API key identifier"
    )
    name = fields.Str(
        description="Human-readable name for this key"
    )
    key_prefix = fields.Str(
        description="First 8 characters of key (safe to display in logs/UI)"
    )
    created_at = fields.DateTime(
        description="When this key was generated"
    )
    last_used_at = fields.DateTime(
        allow_none=True,
        description="When this key was last used for authentication"
    )
    is_active = fields.Bool(
        description="Whether this key is currently valid"
    )


class APIKeyGenerateSchema(Schema):
    """Schema for response when generating a new API key.
    
    ⚠️ IMPORTANT: The full key is shown ONLY ONCE at generation time.
    After this response, the key cannot be retrieved.
    
    Attributes:
        id (str): API key identifier
        name (str): Human-readable name
        key (str): FULL API KEY - shown only once
        key_prefix (str): First 8 characters
        created_at (datetime): Creation timestamp
    """
    id = fields.Str(
        description="Unique API key identifier"
    )
    name = fields.Str(
        description="Human-readable name for this key"
    )
    key = fields.Str(
        description="FULL API KEY - shown only once! Save this securely."
    )
    key_prefix = fields.Str(
        description="First 8 characters of key"
    )
    created_at = fields.DateTime(
        description="When this key was generated"
    )


class APIKeyListSchema(Schema):
    """Schema for list of API keys.
    
    Attributes:
        keys (list): List of APIKeySchema objects
        total (int): Total number of keys for this user
    """
    keys = fields.List(
        fields.Nested(APIKeySchema),
        description="List of API keys"
    )
    total = fields.Int(
        description="Total number of API keys"
    )
