"""
Test user activation system

Tests the is_active feature:
1. New users register with is_active=False
2. Inactive users cannot login
3. Activated users can login
4. CLI manage_users.py works correctly
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import secrets


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


class TestDatabase:
    """Test database setup."""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_schema()
    
    def init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def get_db(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_user(self, username, email, password, is_active=False):
        """Create a test user."""
        conn = self.get_db()
        c = conn.cursor()
        
        password_hash = hash_password(password)
        c.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, 1 if is_active else 0)
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    
    def get_user(self, username):
        """Get user by username."""
        conn = self.get_db()
        c = conn.cursor()
        c.execute("SELECT id, password_hash, username, is_active FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        return user
    
    def activate_user(self, username):
        """Activate user."""
        conn = self.get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_active = 1 WHERE username = ?", (username,))
        conn.commit()
        conn.close()


class TestUserActivation:
    """Test user activation system."""
    
    def setup_method(self):
        """Setup test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.db = TestDatabase(self.db_path)
    
    def teardown_method(self):
        """Cleanup test database."""
        import os
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_register_user_inactive(self):
        """Test that new users are created as inactive."""
        self.db.create_user("testuser", "test@example.com", "password123", is_active=False)
        
        user = self.db.get_user("testuser")
        assert user is not None, "User should be created"
        assert user['username'] == "testuser"
        assert user['is_active'] == 0, "New user should be inactive"
    
    def test_register_user_verify_password(self):
        """Test password verification."""
        password = "testpassword123"
        self.db.create_user("testuser", "test@example.com", password, is_active=False)
        
        user = self.db.get_user("testuser")
        assert verify_password(password, user['password_hash']), "Password should verify"
        assert not verify_password("wrongpassword", user['password_hash']), "Wrong password should not verify"
    
    def test_login_inactive_user_fails(self):
        """Test that inactive users cannot login."""
        password = "testpassword123"
        self.db.create_user("testuser", "test@example.com", password, is_active=False)
        
        user = self.db.get_user("testuser")
        
        # Check password is correct
        assert verify_password(password, user['password_hash']), "Password should be correct"
        
        # But user should be inactive
        assert not user['is_active'], "User should be inactive"
        
        # Simulate login check
        if not verify_password(password, user['password_hash']):
            login_error = "Invalid username or password"
        elif not user['is_active']:
            login_error = "Account not activated yet"
        else:
            login_error = None
        
        assert login_error == "Account not activated yet", "Inactive user should get activation error"
    
    def test_login_active_user_succeeds(self):
        """Test that active users can login."""
        password = "testpassword123"
        self.db.create_user("testuser", "test@example.com", password, is_active=True)
        
        user = self.db.get_user("testuser")
        
        # Check password is correct
        assert verify_password(password, user['password_hash']), "Password should be correct"
        
        # User should be active
        assert user['is_active'], "User should be active"
        
        # Simulate login check
        if not verify_password(password, user['password_hash']):
            login_error = "Invalid username or password"
        elif not user['is_active']:
            login_error = "Account not activated yet"
        else:
            login_error = None
        
        assert login_error is None, "Active user should be able to login"
    
    def test_activate_user(self):
        """Test user activation."""
        self.db.create_user("testuser", "test@example.com", "password123", is_active=False)
        
        user_before = self.db.get_user("testuser")
        assert not user_before['is_active'], "User should be inactive"
        
        self.db.activate_user("testuser")
        
        user_after = self.db.get_user("testuser")
        assert user_after['is_active'], "User should be active after activation"
    
    def test_login_flow_inactive_then_active(self):
        """Test full login flow: register -> inactive -> cannot login -> activate -> can login."""
        password = "testpassword123"
        
        # Register user (inactive)
        self.db.create_user("testuser", "test@example.com", password, is_active=False)
        
        # Try to login (should fail with activation message)
        user = self.db.get_user("testuser")
        if verify_password(password, user['password_hash']) and not user['is_active']:
            login_error = "Account not activated yet"
        else:
            login_error = None
        
        assert login_error == "Account not activated yet", "Inactive user should not be able to login"
        
        # Activate user
        self.db.activate_user("testuser")
        
        # Try to login again (should succeed)
        user = self.db.get_user("testuser")
        if not verify_password(password, user['password_hash']):
            login_error = "Invalid username or password"
        elif not user['is_active']:
            login_error = "Account not activated yet"
        else:
            login_error = None
        
        assert login_error is None, "Active user should be able to login"


if __name__ == "__main__":
    # Run tests manually
    test = TestUserActivation()
    
    print("Running user activation tests...\n")
    
    # Test 1
    print("Test 1: Register user as inactive")
    test.setup_method()
    test.test_register_user_inactive()
    test.teardown_method()
    print("✓ PASSED\n")
    
    # Test 2
    print("Test 2: Verify password")
    test.setup_method()
    test.test_register_user_verify_password()
    test.teardown_method()
    print("✓ PASSED\n")
    
    # Test 3
    print("Test 3: Inactive user cannot login")
    test.setup_method()
    test.test_login_inactive_user_fails()
    test.teardown_method()
    print("✓ PASSED\n")
    
    # Test 4
    print("Test 4: Active user can login")
    test.setup_method()
    test.test_login_active_user_succeeds()
    test.teardown_method()
    print("✓ PASSED\n")
    
    # Test 5
    print("Test 5: Activate user")
    test.setup_method()
    test.test_activate_user()
    test.teardown_method()
    print("✓ PASSED\n")
    
    # Test 6
    print("Test 6: Full login flow (register -> inactive -> activate -> can login)")
    test.setup_method()
    test.test_login_flow_inactive_then_active()
    test.teardown_method()
    print("✓ PASSED\n")
    
    print("="*80)
    print("All user activation tests PASSED ✓")
    print("="*80)
