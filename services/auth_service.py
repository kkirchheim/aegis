"""Authentication service - password hashing, user queries, session logic."""

import hashlib
import secrets
from database import get_db


def hash_password(password):
    """Hash password using PBKDF2."""
    salt = secrets.token_hex(32)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwdhash.hex()}"


def verify_password(password, password_hash):
    """Verify password against stored hash."""
    try:
        salt, pwdhash = password_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == pwdhash
    except:
        return False


def get_user_by_username(username):
    """Get user by username."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, password_hash, username, is_active FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        return None


def get_user_by_id(user_id):
    """Get user by ID."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, password_hash, username, email, is_active, created_at FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        return None


def user_exists(username, email):
    """Check if username or email already exists."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        result = c.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        return False


def create_user(username, email, password):
    """Create new user (inactive by default)."""
    try:
        password_hash = hash_password(password)
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 0)",
            (username, email, password_hash)
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    except Exception as e:
        return None


def update_password(user_id, new_password):
    """Update user password."""
    try:
        new_hash = hash_password(new_password)
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def create_default_admin_user(app_logger=None):
    """
    Create default admin user if it doesn't exist.
    
    SECURITY: Default admin password is randomly generated on first run
    and should be changed immediately after initial login.
    """
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Check if admin user exists
        c.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        admin_user = c.fetchone()
        
        if admin_user:
            if app_logger:
                app_logger.info("✓ Admin user already exists")
        else:
            # Generate random password for admin user
            # This ensures the admin account is unique per deployment
            admin_password = secrets.token_urlsafe(16)  # Random 16-char base64 string
            password_hash = hash_password(admin_password)
            
            c.execute(
                "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
                ("admin", "admin@example.com", password_hash)
            )
            conn.commit()
            
            if app_logger:
                app_logger.warning("=" * 70)
                app_logger.warning("⚠️  DEFAULT ADMIN USER CREATED")
                app_logger.warning("=" * 70)
                app_logger.warning(f"Username: admin")
                app_logger.warning(f"Password: {admin_password}")
                app_logger.warning("⚠️  PLEASE CHANGE THIS PASSWORD IMMEDIATELY!")
                app_logger.warning("=" * 70)
        
        conn.close()
    except Exception as e:
        if app_logger:
            app_logger.error(f"Failed to create default admin user: {e}")
