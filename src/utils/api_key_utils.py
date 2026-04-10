"""Utilities for API key generation and verification."""

import secrets
from hashlib import pbkdf2_hmac
from datetime import datetime

from models.api_key import APIKey
from models.database import db


class APIKeyError(Exception):
    """Base exception for API key operations."""
    pass


class InvalidAPIKeyError(APIKeyError):
    """Raised when API key is invalid or not found."""
    pass


class ExpiredAPIKeyError(APIKeyError):
    """Raised when API key has expired."""
    pass


def generate_api_key() -> str:
    """
    Generate a new API key.
    
    Format: prc_sk_<32 random characters>
    
    Returns:
        str: Full API key (shown only once to user)
    """
    random_part = secrets.token_urlsafe(32)[:32]  # 32 random chars
    return f"prc_sk_{random_part}"


def hash_api_key(api_key: str, salt: str = None) -> tuple[str, str]:
    """
    Hash an API key using PBKDF2.
    
    Args:
        api_key: The API key to hash
        salt: Optional salt (generated if not provided)
    
    Returns:
        tuple: (hashed_key, salt) - both hex-encoded
    """
    if salt is None:
        salt = secrets.token_hex(32)  # 32 random bytes as hex
    
    # PBKDF2: 100k iterations, SHA-256
    hash_bytes = pbkdf2_hmac(
        'sha256',
        api_key.encode(),
        salt.encode(),
        100000
    )
    
    hash_hex = hash_bytes.hex()
    return f"{salt}${hash_hex}", salt


def verify_api_key(api_key: str) -> int:
    """
    Verify an API key and return the user_id.
    
    Args:
        api_key: The API key to verify (full key from Authorization header)
    
    Returns:
        int: User ID associated with this key
    
    Raises:
        InvalidAPIKeyError: If key is invalid, not found, or inactive
        ExpiredAPIKeyError: If key has expired
    """
    if not api_key or not api_key.startswith('prc_sk_'):
        raise InvalidAPIKeyError("Invalid API key format")
    
    try:
        # Hash the incoming key
        hashed_input, salt = hash_api_key(api_key)
        
        # Find key in database by prefix and hash
        key_prefix = api_key[:8]
        db_key = APIKey.select().where(
            (APIKey.key_prefix == key_prefix) &
            (APIKey.is_active == True)
        ).first()
        
        if not db_key:
            raise InvalidAPIKeyError("API key not found or inactive")
        
        # Check if key has expired
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            raise ExpiredAPIKeyError("API key has expired")
        
        # Verify hash using stored salt
        stored_salt = db_key.key_hash.split('$')[0]
        expected_hash, _ = hash_api_key(api_key, stored_salt)
        
        # Use constant-time comparison to prevent timing attacks
        if not _constant_time_compare(expected_hash, db_key.key_hash):
            raise InvalidAPIKeyError("Invalid API key")
        
        # Update last_used_at
        db_key.last_used_at = datetime.utcnow()
        db_key.save()
        
        # Return the user ID (Peewee stores as user_id_id when accessed as raw value)
        # db_key.user_id returns the User object, we need the ID
        return int(db_key.user_id_id) if db_key.user_id_id else int(db_key.user_id.id)
    
    except (InvalidAPIKeyError, ExpiredAPIKeyError):
        raise
    except Exception as e:
        raise InvalidAPIKeyError(f"Failed to verify API key: {str(e)}")


def _constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        bool: True if strings are equal
    """
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    
    return result == 0
