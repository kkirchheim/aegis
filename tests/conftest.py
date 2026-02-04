"""
Pytest configuration and fixtures for Paper Reproducibility Checker tests.

This conftest.py provides:
1. In-memory SQLite database for each test
2. Fresh database and admin user per test
3. Flask test client with proper setup/teardown
4. Session fixtures for authenticated tests
5. User management fixtures
"""

import sys
import os
import pytest
import sqlite3
import tempfile

# Set dummy API key for testing to avoid import-time errors
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-key-for-pytest"

# Add parent directory to path so 'app' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from database import init_db, get_db
from services.auth_service import hash_password, create_user, get_user_by_username
from app import create_app


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to use in-memory database before each test."""
    # Use file-based temp database instead of :memory: to avoid connection isolation issues
    import tempfile
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    
    original_db = Config.DATABASE
    Config.DATABASE = temp_db_path
    
    yield
    
    Config.DATABASE = original_db
    
    # Cleanup temp database file
    try:
        import os
        os.unlink(temp_db_path)
    except:
        pass


@pytest.fixture
def app():
    """Create a Flask app instance for testing."""
    # Use the temp database configured above
    app = create_app()
    app.config['TESTING'] = True
    
    with app.app_context():
        # Initialize fresh database
        init_db()
    
    yield app


@pytest.fixture
def client(app):
    """Create a test client with fresh database."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Provide Flask app context for database operations."""
    with app.app_context():
        yield
        # Clear all tables after test
        try:
            conn = get_db()
            c = conn.cursor()
            
            # Get all table names
            c.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in c.fetchall()]
            
            # Drop all tables
            for table in tables:
                try:
                    c.execute(f"DROP TABLE IF EXISTS {table}")
                except:
                    pass
            
            conn.commit()
            conn.close()
        except:
            pass


@pytest.fixture
def test_user_credentials():
    """Provide test user credentials."""
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword123!'
    }


@pytest.fixture
def admin_user_credentials():
    """Provide test admin credentials."""
    return {
        'username': 'admin',
        'email': 'admin@example.com',
        'password': 'AdminPassword123!'
    }


@pytest.fixture
def create_test_user(client, app):
    """Factory fixture to create test users."""
    def _create_user(username, email, password, is_active=True):
        with app.app_context():
            password_hash = hash_password(password)
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, 1 if is_active else 0)
            )
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            return user_id
    
    return _create_user


@pytest.fixture
def authenticated_user(client, app, create_test_user, test_user_credentials):
    """Create and authenticate a test user."""
    user_id = create_test_user(
        test_user_credentials['username'],
        test_user_credentials['email'],
        test_user_credentials['password'],
        is_active=True
    )
    
    # Set session
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = test_user_credentials['username']
    
    return client


@pytest.fixture
def authenticated_admin(client, app, create_test_user, admin_user_credentials):
    """Create and authenticate an admin user."""
    user_id = create_test_user(
        admin_user_credentials['username'],
        admin_user_credentials['email'],
        admin_user_credentials['password'],
        is_active=True
    )
    
    # Set session
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = admin_user_credentials['username']
    
    return client


@pytest.fixture
def unauthenticated_client(client):
    """Ensure client has no session."""
    with client.session_transaction() as sess:
        sess.clear()
    return client


@pytest.fixture
def multiple_users(client, app, create_test_user):
    """Create multiple test users for multi-user testing."""
    users = []
    for i in range(3):
        user_id = create_test_user(
            f"user{i+1}",
            f"user{i+1}@example.com",
            f"Password{i+1}!",
            is_active=True
        )
        users.append({
            'id': user_id,
            'username': f"user{i+1}",
            'email': f"user{i+1}@example.com",
            'password': f"Password{i+1}!"
        })
    
    return users
