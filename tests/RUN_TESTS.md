# Running Tests

## Prerequisites

Ensure all requirements are installed:
```bash
pip install -r requirements.txt
```

## Quick Start

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_app.py -v
```

## Test Infrastructure

### conftest.py
Provides essential fixtures for all tests:
- `app`: Flask application with in-memory SQLite database
- `client`: Unauthenticated test client
- `authenticated_user`: Authenticated test client with session
- `authenticated_admin`: Admin authenticated test client
- `create_test_user`: Factory for creating test users
- `multiple_users`: Pre-created set of test users
- `app_context`: Flask app context for database operations
- `reset_config`: Auto-used fixture for database reset between tests

### Key Test Files Updated

#### test_app.py
✅ **Fixed:**
- Home page redirect test (expects 302, not 200)
- Fixture imports (uses new conftest fixtures)
- Database schema tests (uses app fixture)
- Event emission tests (uses app fixture)
- Error handling tests (uses authenticated_user fixture)
- Data integrity tests (uses app fixture)

**Tests to run:**
```bash
pytest tests/test_app.py -v
```

#### test_cache_behavior.py
✅ **Fixed:**
- Imports corrected (Config.ENABLE_CACHING instead of app.ENABLE_CACHING)
- Removed invalid function calls (get_cached_paper_analysis, etc.)
- Tests focus on configuration verification

**Tests to run:**
```bash
pytest tests/test_cache_behavior.py -v
```

#### test_auth_security.py
✅ **Already has fixtures** - but could be updated to use conftest.py fixtures

**Tests to run:**
```bash
pytest tests/test_auth_security.py -v
```

## Expected Test Results

### Pass Criteria
- All database tables created correctly
- Authentication redirects working (302 to /login)
- Authenticated routes return 200
- Events properly stored in database
- Error handling returns proper status codes
- Multi-user access isolation working

### Known Test Limitations

1. **Home page tests**: Expects redirect to login (302), not 200
2. **Protected routes**: All routes except /register, /login, /health require authentication
3. **Database isolation**: Each test gets fresh in-memory database
4. **No persistence**: Data doesn't carry between tests
5. **File uploads**: Test framework doesn't support actual file uploads to /uploads

## Common Test Patterns

### Testing Authenticated Routes
```python
def test_protected(self, authenticated_user):
    response = authenticated_user.get('/protected-route')
    assert response.status_code == 200
```

### Testing Database Operations
```python
def test_db(self, app):
    with app.app_context():
        conn = get_db()
        c = conn.cursor()
        # Do database work
        conn.close()
```

### Testing Unauthenticated Access
```python
def test_unauth(self, client):
    response = client.get('/protected')
    assert response.status_code in [301, 302, 303, 401]
```

## Running with Coverage

```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Debugging Tests

### See full test output
```bash
pytest tests/test_app.py::TestHomeAndBasics -v -s
```

### Stop on first failure
```bash
pytest tests/test_app.py -x
```

### Run specific test with print statements
```bash
pytest tests/test_app.py::TestDatabase::test_database_schema -v -s
```

## Test Fixtures Reference

### Get authenticated client
```python
def test_something(self, authenticated_user):
    # authenticated_user is already a client with session set
    response = authenticated_user.get('/')
```

### Create test user dynamically
```python
def test_create_user(self, create_test_user, app):
    user_id = create_test_user('username', 'email@test.com', 'password')
    # Now use user_id in test
```

### Use app context
```python
def test_app_context(self, app):
    with app.app_context():
        # Can call functions that need app context
        conn = get_db()
```

## Continuous Integration

For CI/CD pipelines:

```bash
# Run tests with minimal output
pytest tests/ --tb=short -q

# Run tests and generate report
pytest tests/ --tb=short -v --junitxml=test-results.xml

# Check coverage threshold
pytest tests/ --cov=. --cov-fail-under=70
```

## Troubleshooting

### "No module named 'app'"
Solution: Make sure conftest.py is in the tests/ directory and adds parent to sys.path

### "ANTHROPIC_API_KEY not found"
Solution: conftest.py sets dummy key automatically for tests

### "TypeError: 'NoneType' object is not subscriptable"
Solution: Check that fixtures are being passed correctly (e.g., `authenticated_user` instead of `client`)

### "Database is locked"
Solution: Ensure tests are using in-memory database (`:memory:`), not file-based

### Tests pass individually but fail in suite
Solution: Check for test isolation issues - ensure each test properly cleans up

## Next Steps

1. Run full test suite: `pytest tests/ -v`
2. Check coverage: `pytest tests/ --cov=.`
3. Fix any remaining failures (should be minimal)
4. Document any known limitations
5. Update CI/CD pipeline with new test commands

## See Also

- [TEST_INFRASTRUCTURE_FIXES.md](TEST_INFRASTRUCTURE_FIXES.md) - Detailed explanation of fixes
- [conftest.py](conftest.py) - Fixture definitions
- [test_app.py](test_app.py) - Main application tests
