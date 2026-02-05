"""Marshmallow schemas for admin operations."""

from marshmallow import Schema, fields, validate


class UserSchema(Schema):
    """Schema for user representation in admin operations.
    
    Attributes:
        id: Unique user identifier
        username: User's login name
        email: User's email address
        is_active: Whether the user account is active
        is_admin: Whether the user has admin privileges
        created_at: Timestamp when the user account was created
        last_login: Timestamp of the user's last login
    """
    
    id = fields.Int(allow_none=True)
    username = fields.Str(allow_none=True)
    email = fields.Email(allow_none=True)
    is_active = fields.Bool(allow_none=True)
    is_admin = fields.Bool(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    last_login = fields.DateTime(allow_none=True)


class UserListSchema(Schema):
    """Schema for a paginated list of users.
    
    Attributes:
        users: List of nested UserSchema objects
        total: Total count of users
    """
    
    users = fields.List(fields.Nested(UserSchema), allow_none=True)
    total = fields.Int(allow_none=True)


class UserActionSchema(Schema):
    """Schema for the response to an admin user action.
    
    Attributes:
        ok: Whether the action was successful
        message: Human-readable message about the action result
        user_id: ID of the user that was affected by the action
    """
    
    ok = fields.Bool(allow_none=True)
    message = fields.Str(allow_none=True)
    user_id = fields.Int(allow_none=True)


# ============================================================================
# INPUT VALIDATION SCHEMAS
# ============================================================================

class UpdateUserStatusSchema(Schema):
    """Schema for updating user status (activate/deactivate).
    
    Attributes:
        is_active (bool): Whether user account is active (required)
    """
    
    is_active = fields.Bool(
        required=True,
        description="Whether user account is active"
    )
