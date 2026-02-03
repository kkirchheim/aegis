# Testing Guide

## Running Tests

### Prerequisites
Tests run in Docker and require no API credentials (uses dummy key).

### Run All Tests
```bash
docker-compose exec app pytest tests/ -v
```

### Run Specific Test File
```bash
# Test Flask app routes and database
docker-compose exec app pytest tests/test_app.py -v

# Test agent API responses
docker-compose exec app pytest tests/test_agent_api.py -v
```

### Run Specific Test Class
```bash
docker-compose exec app pytest tests/test_app.py::TestUploadEndpoint -v
```

### Run Specific Test
```bash
docker-compose exec app pytest tests/test_app.py::TestUploadEndpoint::test_upload_creates_job -v
```

### With Coverage Report
```bash
docker-compose exec app pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html
```

## Test Suite Overview

### test_app.py (20 tests)
Tests Flask backend routes and database operations:

- **TestHomeAndBasics** (2 tests) - Home page loads, job list works
- **TestDatabase** (3 tests) - Schema validation, column checks
- **TestEventEmission** (1 test) - Events stored correctly
- **TestStageEvents** (2 tests) - All three stages emit events
- **TestJobRoutes** (2 tests) - Job creation and retrieval
- **TestErrorHandling** (3 tests) - API error responses
- **TestDataIntegrity** (2 tests) - Data stored correctly
- **TestPaperAnalysisStorage** (1 test) - Paper metadata persisted
- **TestArtifactStorage** (1 test) - Code artifacts stored
- **TestNoneHandling** (2 tests) - Null values handled gracefully
- **TestJsonSerialization** (1 test) - Responses are JSON-serializable

### test_agent_api.py (17 tests)
Tests agent API and prompt building:

- **TestAgentThink** (9 tests) - Agent decision requests validated
- **TestAgentLog** (3 tests) - Agent logging endpoints
- **TestPrompBuilding** (1 test) - Context truncation works
- **TestDebugLogging** (1 test) - Parse failures logged
- **TestMalformedResponses** (1 test) - Invalid JSON handled

## CI/CD Integration

### GitLab CI

Tests run automatically on `git push`:

```yaml
# .gitlab-ci.yml
test:
  stage: test
  script:
    - pip install -r requirements.txt
    - pytest tests/ -v --cov=. --cov-report=xml
```

No API credentials required—conftest.py sets dummy key for CI environments.

## Local Development

### Watch Tests (Auto-run on File Change)
```bash
pip install pytest-watch
ptw tests/
```

### Debug a Test
```bash
docker-compose exec app pytest tests/test_app.py::TestUploadEndpoint::test_upload_creates_job -v -s
# -s shows print() output
```

### Create a New Test

1. Add test function to `tests/test_app.py` or `tests/test_agent_api.py`
2. Use fixtures from `conftest.py`
3. Run: `docker-compose exec app pytest tests/test_*.py::TestClass::test_name -v`

Example:
```python
def test_example(client):
    """Test description"""
    response = client.get('/')
    assert response.status_code == 200
```

## Performance

- All 37 tests complete in ~45 seconds
- Each test uses fresh SQLite database (no shared state)
- Tests are deterministic and can run in parallel

## Coverage

Target: 75%+ coverage on core modules

Run coverage:
```bash
docker-compose exec app pytest tests/ --cov=app --cov-report=term-missing
```

View detailed report:
```bash
docker-compose exec app pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

## Troubleshooting Tests

### Tests Hang
```bash
# Increase timeout
docker-compose exec app pytest tests/ --timeout=30
```

### Import Errors
```bash
# Verify conftest.py sets path and API key
cat tests/conftest.py

# Check module available
docker-compose exec app python -c "import app; print(app)"
```

### Database Locked
```bash
# Database is fresh per test, shouldn't happen
# If it does, delete and restart:
docker-compose down -v
docker-compose up -d app
docker-compose exec app pytest tests/ -v
```
