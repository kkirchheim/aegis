"""Authentication schemas for user login, registration, and password management.

This module contains Marshmallow schemas for validating authentication-related
requests and responses, including user registration, login, password changes,
and session information.
"""

from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    """Schema for user login validation.
    
    Validates the credentials required for user authentication.
    """
    username = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        description="Username for authentication"
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=6),
        description="Password (minimum 6 characters)"
    )


class RegisterSchema(Schema):
    """Schema for user registration validation.
    
    Validates the information required to create a new user account,
    including password confirmation.
    """
    username = fields.Str(
        required=True,
        description="Desired username for the new account"
    )
    email = fields.Email(
        required=True,
        description="Email address for the new account"
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8),
        description="Password (minimum 8 characters)"
    )
    confirm_password = fields.Str(
        required=True,
        description="Password confirmation (must match password)"
    )


class ChangePasswordSchema(Schema):
    """Schema for password change validation.
    
    Validates the information required to change a user's password,
    including the old password verification and new password confirmation.
    """
    old_password = fields.Str(
        required=True,
        description="Current password for verification"
    )
    new_password = fields.Str(
        required=True,
        validate=validate.Length(min=8),
        description="New password (minimum 8 characters)"
    )
    confirm_password = fields.Str(
        required=True,
        description="New password confirmation (must match new_password)"
    )


class SessionSchema(Schema):
    """Schema for session response validation.
    
    Validates and describes the information returned in session responses,
    including user details and navigation information.
    """
    message = fields.Str(
        allow_none=True,
        description="Session status or message"
    )
    redirect = fields.Str(
        allow_none=True,
        description="Redirect URL after successful authentication"
    )
    user_id = fields.Int(
        allow_none=True,
        description="Unique user identifier"
    )
    username = fields.Str(
        allow_none=True,
        description="Username of authenticated user"
    )
