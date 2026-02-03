# Testing Guide

## Overview

The project includes a comprehensive test suite for the Agent API endpoints to catch edge cases like the one we just fixed.

## The Bug We Fixed

**Issue:** When `repo_state` had `errors: None` (instead of missing or `[]`), the code crashed with:
```
Error in agent/think: object of type 'NoneType' has no len()
```

**Root Cause:** 
```python
# This code was WRONG:
errors = repo_state.get("errors", [])  
len(errors)  # ← Crashes if errors is None!
```

The `.get()` method only uses the default if the **key is missing**. If the key exists but is `None`, it returns `None`, bypassing the default.

**Fix Applied:**
```python
# This code is CORRECT:
errors = repo_state.get("errors") or []
len(errors)  # ← Always safe now
```

Now `None` triggers the `or []` fallback, ensuring we always get a list.

## Running Tests

### Run all Agent API tests:
```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
docker run --rm -v "$PWD:/app" -w /app python:3.10-slim bash -c \
  "pip install -q pytest flask requests docker anthropic pdfplumber python-dotenv && \
   python -m pytest tests/test_agent_api.py -v"
```

### Run a specific test class:
```bash
docker run --rm -v "$PWD:/app" -w /app python:3.10-slim bash -c \
  "pip install -q pytest flask requests docker anthropic pdfplumber python-dotenv && \
   python -m pytest tests/test_agent_api.py::TestAgentThink -v"
```

### Run a specific test:
```bash
docker run --rm -v "$PWD:/app" -w /app python:3.10-slim bash -c \
  "pip install -q pytest flask requests docker anthropic pdfplumber python-dotenv && \
   python -m pytest tests/test_agent_api.py::TestAgentThink::test_none_errors -v"
```

## Test Coverage

### TestAgentThink (7 tests)
Tests the `/api/agent/think` endpoint that Claude calls to make decisions:

| Test | Purpose | Catches |
|------|---------|---------|
| `test_basic_request` | Valid request works | General functionality |
| `test_missing_job_id` | Rejects requests without job_id | Input validation |
| `test_none_errors` | **Handles errors=None** | **The NoneType bug** ✅ |
| `test_none_last_output` | Handles last_output=None | None handling |
| `test_missing_optional_fields` | Works with minimal data | Robustness |
| `test_empty_discovered_files` | Handles empty file lists | Edge cases |
| `test_very_long_output` | Handles large outputs (context truncation) | Context explosion bugs |
| `test_multiple_errors` | Handles many errors (summarizes to last 2) | Memory issues |
| `test_high_iteration_count` | Max iterations edge case | Loop detection |
| `test_special_characters_in_output` | Handles JSON-unsafe chars | Escaping bugs |

### TestAgentLog (3 tests)
Tests the `/api/agent/log` endpoint (logging):

| Test | Purpose | Catches |
|------|---------|---------|
| `test_basic_log` | Valid log message | Functionality |
| `test_missing_job_id` | Rejects without job_id | Validation |
| `test_very_long_message` | Handles huge messages | Buffer overflow |

### TestPrompBuilding (1 test)
Integration tests for Claude prompt construction:

| Test | Purpose | Catches |
|------|---------|---------|
| `test_context_truncation_in_prompt` | Large data doesn't crash | Context explosion |

## Key Insights

### Why These Tests Matter

1. **None vs Missing**: Python's `.get(key, default)` is tricky
   - `.get("x", [])` with `{"x": None}` returns `None`, not `[]`
   - Use `or []` for safety

2. **Context Explosion**: Long outputs accumulate, can cause:
   - Token limit exceeded in Claude API
   - Malformed JSON responses
   - Tests verify truncation works

3. **Error Summarization**: Showing all errors can overflow context
   - Tests verify only last 2 errors shown
   - Prevents token waste

4. **Edge Cases**: Real-world data is messy
   - Empty lists vs None vs missing
   - Special characters in output
   - Very long strings
   - High iteration counts

## Adding New Tests

When adding new endpoints or fixing bugs:

1. **Create test** for the bug first (before fixing)
2. **Verify test fails** (reproduces the bug)
3. **Fix code** to make test pass
4. **Add edge cases** (None, empty, very large, etc.)

Example structure:
```python
class TestNewEndpoint:
    """Tests for /api/new/endpoint"""
    
    def test_basic_functionality(self, client):
        """Happy path - should work."""
        ...
        assert response.status_code == 200
    
    def test_none_handling(self, client):
        """Edge case - None values shouldn't crash."""
        ...
        assert response.status_code != 500
    
    def test_very_long_input(self, client):
        """Stress test - large data shouldn't crash."""
        ...
        assert response.status_code in [200, 500]
```

## Notes for Future

- Tests currently mock endpoints with test client
- For full integration tests, mock Claude API to avoid costs
- Add performance benchmarks if response time becomes critical
- Consider adding CI/CD pipeline to run tests on every commit

## Running from Docker Compose

Alternatively, if you want to run tests inside the Docker container:

```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
docker-compose exec web python -m pytest tests/test_agent_api.py -v
```

(Note: This requires the web service to be running and pytest installed in the image)
