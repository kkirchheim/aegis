"""API Key model for external application authentication."""

import uuid
from datetime import datetime
from peewee import CharField, ForeignKeyField, BooleanField, DateTimeField, UUIDField

from models.database import BaseModel, User


class APIKey(BaseModel):
    """API key for authenticating external applications.
    
    Attributes:
        id: Unique API key identifier (UUID)
        user_id: Foreign key to User
        name: Human-readable name (e.g., "CLI Tool", "Integration Service")
        key_hash: PBKDF2-hashed key (never store plaintext)
        key_prefix: First 8 characters of key (safe to display/log)
        is_active: Whether this key is currently valid
        created_at: When this key was generated
        last_used_at: When this key was last used for authentication
        expires_at: Optional expiration date (null = no expiry)
    """
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = ForeignKeyField(User, backref='api_keys')
    name = CharField(max_length=100)
    key_hash = CharField()  # PBKDF2 hashed with salt
    key_prefix = CharField(max_length=8)  # First 8 chars of key (safe to display)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    last_used_at = DateTimeField(null=True, default=None)
    expires_at = DateTimeField(null=True, default=None)
    
    class Meta:
        table_name = 'api_keys'
        indexes = (
            (('user_id', 'is_active'), False),  # Query active keys by user
            (('key_hash',), True),  # Unique key hash for lookup
        )
