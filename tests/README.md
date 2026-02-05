# Test Suite Organization

## Overview

The test suite for Paper Reproducibility Checker is organized for clarity and efficiency. Tests are categorized by type (unit, integration) and can be filtered using pytest markers for flexible test execution.

## Directory Structure

```
tests/
├── unit/                    # Unit tests with mocked dependencies
├── integration/             # Integration tests with real services
├── fixtures/                # Test data factories and shared fixtures
│   ├── __init__.py
│   ├── factories.py         # Factory functions for test objects
│   └── conftest.py          # Fixture definitions (inherited from parent)
├── conftest.py              # Shared pytest configuration and fixtures
├── test_api.py              # API endpoint tests
├── test_auth.py             # Authentication tests
├── test_services.py         # Service layer tests
└── [other test files]
```

## Running Tests

### All Tests
```bash
pytest tests/
```

### Only Unit Tests
```bash
pytest tests/unit/ -m unit
```

### Only Integration Tests
```bash
pytest tests/integration/ -m integration
```

### Skip Slow Tests
```bash
pytest tests/ -m "not slow"
```

### Specific Test File
```bash
pytest tests/unit/test_services.py -v
```

### Specific Test Function
```bash
pytest tests/unit/test_services.py::test_user_creation -v
```

### By Marker (Multiple)
```bash
# API tests excluding slow ones
pytest tests/ -m "api and not slow"

# Auth tests
pytest tests/ -m auth

# Database tests
pytest tests/ -m db
```

## Pytest Markers

Markers allow filtering tests by category. Add markers to your test functions:

```python
@pytest.mark.unit
def test_simple_logic():
    """Fast unit test with mocks."""
    pass

@pytest.mark.integration
def test_with_real_service():
    """Integration test with real database."""
    pass

@pytest.mark.slow
def test_long_running_operation():
    """Slow test, skip with -m 'not slow'."""
    pass

@pytest.mark.db
def test_database_operation():
    """Requires database access."""
    pass

@pytest.mark.api
def test_api_endpoint():
    """Tests API endpoint."""
    pass

@pytest.mark.auth
def test_authentication():
    """Tests authentication logic."""
    pass

@pytest.mark.event
def test_event_streaming():
    """Tests event/streaming functionality."""
    pass
```

## Available Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `@pytest.mark.unit` | Unit test (fast, mocked) | Isolated logic tests |
| `@pytest.mark.integration` | Integration test (slower, real services) | End-to-end flows |
| `@pytest.mark.slow` | Slow test | Long-running operations |
| `@pytest.mark.db` | Requires database | Database operations |
| `@pytest.mark.api` | Tests API endpoints | HTTP endpoint tests |
| `@pytest.mark.auth` | Authentication test | Auth logic tests |
| `@pytest.mark.event` | Event/streaming test | SSE/polling tests |

## Fixtures

### Common Fixtures (from conftest.py)

#### Application & Client
- `app` - Flask application instance
- `client` - Flask test client
- `app_context` - Flask app context for DB operations

#### Authentication
- `authenticated_user` - Test client with authenticated session
- `authenticated_admin` - Test client with admin session
- `unauthenticated_client` - Test client with no session
- `test_user_credentials` - Default test user credentials
- `admin_user_credentials` - Default admin credentials

#### User Management
- `create_test_user` - Factory fixture to create test users
- `multiple_users` - Creates 3 test users for multi-user testing
- `authenticated_user_id` - Extract user ID from authenticated session

#### Database
- `peewee_test_db` - In-memory Peewee ORM database
- `create_test_job` - Factory fixture to create test jobs
- `create_test_event` - Factory fixture to create test events

#### Mocks
- `mock_llm_provider` - Mock Anthropic API client
- `mock_docker_service` - Mock Docker client
- `mock_analysis_service` - Mock analysis service
- `mock_evaluation_service` - Mock evaluation service
- `mock_job_service` - Mock job service
- `mock_event_dispatcher` - Mock event dispatcher
- `mock_event_queues` - Mock SSE event queues

### Using Fixtures

```python
def test_create_job(authenticated_user, create_test_job):
    """Test job creation."""
    job = create_test_job(status="processing")
    assert job.status == "processing"

def test_with_multiple_users(multiple_users):
    """Test with multiple users."""
    assert len(multiple_users) == 3
    assert all(u['is_active'] for u in multiple_users)

def test_with_mocks(mock_llm_provider, mock_docker_service):
    """Test with mocked external services."""
    mock_llm_provider.analyze.return_value = {"score": 0.8}
    # Use mocks in your test
```

## Factory Functions (from fixtures/factories.py)

### Simple Factories

```python
from tests.fixtures.factories import (
    create_test_user,
    create_test_job,
    create_test_event,
    create_test_pdf_file,
    create_test_auth_headers,
)

def test_with_factory(app, create_test_user):
    user_id = create_test_user(app, create_test_user, username="alice", password="Secret!")
    # Use user_id in test
```

### Fluent API Factories

```python
from tests.fixtures.factories import UserFactory, JobFactory

def test_with_fluent_factory(app, create_test_user, peewee_test_db):
    # Create user with fluent API
    user_id = UserFactory(app, create_test_user) \
        .with_username("alice") \
        .with_email("alice@example.com") \
        .build()
    
    # Create job with fluent API
    job = JobFactory(app, peewee_test_db, user_id=user_id) \
        .with_status("processing") \
        .with_stage("analysis") \
        .build()
```

## Best Practices

### 1. Use Appropriate Markers
```python
@pytest.mark.unit  # Fast, mocked
def test_calculation():
    assert 2 + 2 == 4
```

### 2. Organize by Type
- Keep unit tests in `tests/unit/`
- Keep integration tests in `tests/integration/`
- Keep shared tests in `tests/`

### 3. Use Fixtures for Setup
```python
@pytest.mark.unit
def test_with_fixture(authenticated_user, create_test_job):
    """Use fixtures instead of manual setup."""
    job = create_test_job(status="complete")
    assert job.status == "complete"
```

### 4. Use Factories for Complex Objects
```python
from tests.fixtures.factories import JobFactory

@pytest.mark.integration
def test_job_processing(app, peewee_test_db, create_test_user):
    """Use factories for readable test setup."""
    user_id = create_test_user(app, create_test_user)
    job = JobFactory(app, peewee_test_db, user_id) \
        .with_status("pending") \
        .build()
```

### 5. Mock External Services
```python
@pytest.mark.unit
def test_analysis_without_llm(mock_llm_provider):
    """Test logic without calling real API."""
    mock_llm_provider.analyze.return_value = {"score": 0.9}
    # Test your code
```

### 6. Clean Up After Tests
```python
@pytest.mark.db
def test_database_operation(app, peewee_test_db):
    """Database fixtures auto-cleanup after test."""
    # Database is fresh per test
    # Cleanup is automatic
```

## Running Tests in CI/CD

### Quick Run (skip slow tests)
```bash
pytest tests/ -m "not slow" -v
```

### Full Run
```bash
pytest tests/ -v --cov=app --cov=services --cov=models
```

### Grouped by Type
```bash
# Unit tests only
pytest tests/unit/ -m unit -v

# Integration tests only (slower)
pytest tests/integration/ -m integration -v
```

## Debugging Tests

### Run with Output
```bash
pytest tests/test_api.py -v -s
```

### Stop on First Failure
```bash
pytest tests/ -x
```

### Enter Debugger on Failure
```bash
pytest tests/ --pdb
```

### Show Local Variables on Failure
```bash
pytest tests/ -l
```

### Capture Logs
```bash
pytest tests/ --log-cli-level=DEBUG
```

## Common Test Patterns

### Testing API Endpoints
```python
@pytest.mark.api
def test_create_job_endpoint(authenticated_user):
    """Test POST /api/jobs endpoint."""
    response = authenticated_user.post('/api/jobs', json={'pdf': 'file.pdf'})
    assert response.status_code == 201
    assert 'job_id' in response.json
```

### Testing Database Operations
```python
@pytest.mark.db
def test_create_job(app, peewee_test_db, create_test_user):
    """Test job creation in database."""
    user_id = create_test_user(app, create_test_user)
    job = Job.create(user_id=user_id, status="pending")
    assert Job.select().where(Job.id == job.id).exists()
```

### Testing with Mocks
```python
@pytest.mark.unit
def test_analysis_service(mock_llm_provider, mock_docker_service):
    """Test service with mocked dependencies."""
    mock_llm_provider.analyze.return_value = {"score": 0.8}
    # Test your service code
```

### Testing Authentication
```python
@pytest.mark.auth
def test_protected_endpoint(authenticated_user, unauthenticated_client):
    """Test that endpoint requires authentication."""
    # Should work with auth
    response = authenticated_user.get('/api/jobs')
    assert response.status_code == 200
    
    # Should fail without auth
    response = unauthenticated_client.get('/api/jobs')
    assert response.status_code == 401
```

## Troubleshooting

### Database Isolation Issues
Each test gets a fresh database via `peewee_test_db` fixture. Tests don't interfere with each other.

### Fixture Scope
- `function` scope (default): Fresh fixture per test function
- `session` scope: Shared across all tests (use cautiously)
- `module` scope: Shared within a module

### Common Issues

**"Database is locked"**
→ Use the provided `peewee_test_db` fixture, not manual DB setup

**"User not found"**
→ Use `authenticated_user` or `create_test_user` fixtures

**"Fixture not found"**
→ Make sure conftest.py is in tests/ directory

## Contributing Tests

When adding new tests:
1. ✅ Use appropriate markers (`@pytest.mark.unit` or `@pytest.mark.integration`)
2. ✅ Use existing fixtures to avoid duplication
3. ✅ Use factories for complex test object creation
4. ✅ Keep unit tests fast (< 1 second)
5. ✅ Mark slow tests with `@pytest.mark.slow`
6. ✅ Place tests in `unit/` or `integration/` subdirectory when appropriate
7. ✅ Write descriptive test names and docstrings

Example new test:
```python
@pytest.mark.unit
def test_job_status_validation(create_test_job):
    """Unit test: validate job status transitions."""
    job = create_test_job(status="pending")
    assert job.status == "pending"
```

## See Also

- `conftest.py` - Fixture definitions
- `fixtures/factories.py` - Factory functions
- pytest documentation: https://docs.pytest.org/
- Flask testing: https://flask.palletsprojects.com/testing/
