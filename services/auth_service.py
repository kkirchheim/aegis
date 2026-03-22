"""Authentication service - password hashing, user queries, session logic."""

import hashlib
import secrets
from repositories import UserRepository
from models.database import User


def hash_password(password):
    """Hash password using PBKDF2."""
    salt = secrets.token_hex(32)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwdhash.hex()}"


def verify_password(password, password_hash):
    """Verify password against stored hash."""
    import hmac
    try:
        salt, pwdhash = password_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(new_hash.hex(), pwdhash)
    except (ValueError, AttributeError):
        return False


def get_user_by_username(username):
    """Get user by username."""
    return UserRepository.get_by_username(username)


def get_user_by_id(user_id):
    """Get user by ID."""
    return UserRepository.get_by_id(user_id)


def user_exists(username, email):
    """Check if username or email already exists."""
    return UserRepository.exists(username, email)


def create_user(username, email, password):
    """Create new user (inactive by default). Returns user_id or None."""
    password_hash = hash_password(password)
    return UserRepository.create(username, email, password_hash)


def update_password(user_id, new_password):
    """Update user password."""
    new_hash = hash_password(new_password)
    return UserRepository.update_password(user_id, new_hash)


def create_default_admin_user(app_logger=None):
    """
    Create default admin user if it doesn't exist.
    
    SECURITY: Default admin password is randomly generated on first run
    and should be changed immediately after initial login.
    """
    try:
        # Check if admin user exists
        admin_user = UserRepository.get_by_username("admin")
        
        if admin_user:
            if app_logger:
                app_logger.info("✓ Admin user already exists")
        else:
            # Generate random password for admin user
            admin_password = secrets.token_urlsafe(16)
            
            # Create admin user
            User.create(
                username="admin",
                email="admin@example.com",
                password_hash=hash_password(admin_password),
                is_active=True
            )
            
            if app_logger:
                app_logger.warning("=" * 70)
                app_logger.warning("⚠️  DEFAULT ADMIN USER CREATED")
                app_logger.warning("=" * 70)
                app_logger.warning(f"Username: admin")
                app_logger.warning(f"Password: {admin_password}")
                app_logger.warning("⚠️  PLEASE CHANGE THIS PASSWORD IMMEDIATELY!")
                app_logger.warning("=" * 70)
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"Failed to create default admin user: {e}")
