"""Input validation utilities."""


def validate_username(username):
    """Validate username format."""
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters"
    return True, None


def validate_email(email):
    """Validate email format."""
    if not email or "@" not in email:
        return False, "Invalid email"
    return True, None


def validate_password(password):
    """Validate password strength."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    return True, None


def validate_passwords_match(password, confirm_password):
    """Validate passwords match."""
    if password != confirm_password:
        return False, "Passwords don't match"
    return True, None


def validate_storage_limit(storage_limit):
    """
    Validate and normalize storage limit.
    
    Args:
        storage_limit: Storage limit value (int or string)
        
    Returns:
        Tuple of (is_valid, normalized_value, error_message)
    """
    try:
        storage_limit = int(storage_limit)
        if storage_limit < 1 or storage_limit > 100:
            return False, 10, "Storage limit must be between 1 and 100 GB"
        return True, storage_limit, None
    except (ValueError, TypeError):
        return False, 10, "Invalid storage limit value"
