# Test Infrastructure Fixes

## Overview

This document describes the fixes applied to the test infrastructure in the Paper Reproducibility Checker project.

## Problems Fixed

### 1. Database Management
**Problem:** Tests were using temporary files instead of in-memory SQLite databases, and there was no proper cleanup between tests.

**Solution:**
- Updated `conftest.py` to use `:memory:` SQLite database for all tests
- Added `reset_config()` fixture with `autouse=True` to reset database before each test
- Database is automatically created fresh for each test using the `app` fixture

### 2. Test Imports
**Problem:** Tests were importing from incorrect modules:
- `app.ENABLE_CACHING` instead of `config.Config.ENABLE_CACHING`
- Duplicated fixture code across multiple test files

**Solution:**
- Created comprehensive `conftest.py` with reusable fixtures
- All tests now import from correct modules:
  - `from config import Config` for configuration
  - `from database import init_db, get_db` for database functions
  - `from blueprints.jobs import emit_event` for event emission

### 3. Authentication & Authorization
**Problem:** Tests assumed home page (/) returns 200, but now it redirects to login (302) for unauthenticated users.

**Solution:**
- Updated `test_app.py` to expect 302 redirect for unauthenticated home page access
- Added `authenticated_user` fixture for tests that require authentication
- Tests now properly test both authenticated and unauthenticated paths

### 4. Fixture Standardization
**Problem:** Each test file had its own fixture implementations with code duplication.

**Solution:**
- Created central `conftest.py` with pytest fixtures:
  - `app`: Fresh Flask app with in-memory database
  - `client`: Test client without authentication
  - `authenticated_user`: Test client with authenticated session
  - `authenticated_admin`: Test client with admin session
  - `create_test_user`: Factory for creating test users
  - `test_user_credentials`: Standard test user data
  - `admin_user_credentials`: Standard admin user data
  - `multiple_users`: Multiple test users for multi-user testing

## Updated Test Files

### conftest.py
Complete rewrite with:
- Proper in-memory database setup
- Fresh database per test (autouse fixture)
- User management fixtures
- Session fixtures for authenticated tests
- User factory fixture for creating test users with custom credentials

### test_app.py
Changes:
- Updated `TestHomeAndBasics::test_home_page` to expect 302 redirect
- Added test for authenticated home page access (200)
- Updated all fixtures to use new `app` fixture instead of `client`
- Added `user_id` to job creation (required for multi-user support)
- Fixed imports: removed duplicated fixture code

### test_cache_behavior.py
Changes:
- Fixed import: `from config import Config` instead of trying to import from `app`
- Removed references to non-existent functions (`app.get_cached_paper_analysis`, etc.)
- Simplified to verify configuration only

## How to Write Tests Now

### Basic Test Structure
```python
import pytest
from database import get_db

class TestMyFeature:
    def test_something(self, app):
        """Test that uses app fixture."""
        with app.app_context():
            conn = get_db()
            # Do test work
            conn.close()
```

### Authenticated Tests
```python
def test_protected_route(self, authenticated_user):
    """Test protected route with authenticated user."""
    response = authenticated_user.get('/protected')
    assert response.status_code == 200
```

### User Creation Tests
```python
def test_user_operations(self, create_test_user):
    """Test with created users."""
    user_id = create_test_user(
        "testuser",
        "test@example.com",
        "TestPassword123!",
        is_active=True
    )
    # Use user_id in tests
```

### Multi-User Tests
```python
def test_multi_user_access(self, multiple_users):
    """Test with multiple users."""
    for user in multiple_users:
        user_id = user['id']
        username = user['username']
        # Test user-specific behavior
```

## Fixture Dependencies

Fixtures are automatically provided by conftest.py. Here's how they work:

```
app (in-memory database)
  ├── client (unauthenticated)
  ├── authenticated_user (user session + client)
  ├── authenticated_admin (admin session + client)
  ├── create_test_user (factory)
  └── multiple_users (list of 3 users)
```

## Database Behavior

Each test:
1. Gets fresh in-memory database from `app` fixture
2. Uses `reset_config()` to ensure clean state before test
3. Tables are automatically created by `init_db()`
4. Cleanup happens automatically after test (conftest `app_context` fixture)

## Import Guidelines

✅ **Correct Imports**
```python
from config import Config                    # Configuration
from database import init_db, get_db        # Database functions
from services.auth_service import hash_password  # Auth functions
from blueprints.jobs import emit_event      # Event emission
```

❌ **Incorrect Imports (Don't Use)**
```python
from app import ENABLE_CACHING              # Should be Config.ENABLE_CACHING
import app as app_module                    # Avoid direct app module imports
app.ENABLE_CACHING                          # Should be Config.ENABLE_CACHING
```

## Authentication Test Requirements

Tests now must account for authentication redirects:

```python
# Unauthenticated access to protected routes
response = client.get('/')
assert response.status_code == 302  # Redirect to login

# Authenticated access to protected routes
response = authenticated_user.get('/')
assert response.status_code == 200  # Normal response
```

## Debugging Tests

### View test database
```python
def test_debug(self, app):
    with app.app_context():
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        print(c.fetchall())
        conn.close()
```

### Test isolation verification
Each test gets a fresh `:memory:` database, so tests cannot interfere with each other.

### Session debugging
```python
def test_session(self, authenticated_user):
    with authenticated_user.session_transaction() as sess:
        print(sess)  # View session data
```

## Known Limitations

1. **In-Memory Database**: Data doesn't persist between tests. Use fixtures to set up data before each test.
2. **No Fixtures Between Classes**: Each test class should be independent. Use fixtures in `conftest.py` for shared setup.
3. **API Routes**: Tests expecting JSON responses should handle cases where route might return HTML (depends on route implementation).

## Running Tests

```bash
# All tests
python -m pytest tests/

# Specific test file
python -m pytest tests/test_app.py

# Specific test class
python -m pytest tests/test_app.py::TestDatabase

# Specific test
python -m pytest tests/test_app.py::TestDatabase::test_database_schema

# With verbose output
python -m pytest tests/test_app.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

## Test Coverage Goals

- Aim for >90% pass rate
- All protected routes must require authentication
- Multi-user access must be properly isolated
- Database tables must be properly initialized
- Events must be properly stored

## Future Improvements

1. Consider adding fixtures for job creation
2. Add fixtures for file uploads
3. Create markers for slow/integration tests
4. Add fixtures for Docker-dependent tests
5. Create performance benchmarks
