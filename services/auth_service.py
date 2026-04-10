"""Authentication service - password hashing, user queries, session logic."""

import hashlib
import os
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
    Create or update admin user on startup.

    Credentials can be configured via environment variables:
        ADMIN_USERNAME  (default: "admin")
        ADMIN_PASSWORD  (default: randomly generated)
        ADMIN_EMAIL     (default: "admin@example.com")

    When ADMIN_PASSWORD is set, the password is re-applied on every startup
    so that container restarts converge to the configured state.
    """
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

    try:
        admin_user = UserRepository.get_by_username(admin_username)

        if admin_user:
            if admin_password:
                # Re-apply configured password so container restarts stay in sync
                UserRepository.update_password(admin_user.id, hash_password(admin_password))
                if app_logger:
                    app_logger.info(f"✓ Admin user '{admin_username}' exists — password synced from environment")
            else:
                if app_logger:
                    app_logger.info(f"✓ Admin user '{admin_username}' already exists")
        else:
            password_from_env = admin_password is not None
            if not admin_password:
                admin_password = secrets.token_urlsafe(16)

            User.create(
                username=admin_username,
                email=admin_email,
                password_hash=hash_password(admin_password),
                is_active=True,
            )

            if app_logger:
                if password_from_env:
                    app_logger.info(f"✓ Admin user '{admin_username}' created from environment config")
                else:
                    app_logger.warning("=" * 70)
                    app_logger.warning("⚠️  DEFAULT ADMIN USER CREATED")
                    app_logger.warning("=" * 70)
                    app_logger.warning(f"Username: {admin_username}")
                    app_logger.warning(f"Password: {admin_password}")
                    app_logger.warning("⚠️  PLEASE CHANGE THIS PASSWORD IMMEDIATELY!")
                    app_logger.warning("=" * 70)

    except Exception as e:
        if app_logger:
            app_logger.error(f"Failed to create default admin user: {e}")
