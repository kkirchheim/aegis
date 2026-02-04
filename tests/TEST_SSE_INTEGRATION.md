# SSE Integration Tests Documentation

## Overview

This document describes the integration tests for Server-Sent Events (SSE) event streaming in the Paper Reproducibility Checker.

The test suite (`test_sse_integration.py`) contains **20 comprehensive tests** across **11 test classes** that verify:

1. ✅ **Event Persistence** - Events persist to database immediately when emitted
2. ✅ **Historical Events** - SSE endpoint returns all historical events on connection
3. ✅ **Live Streaming** - New events stream to clients in real-time
4. ✅ **Event Ordering** - Events appear in correct chronological order
5. ✅ **Race Conditions** - Events emitted before SSE connects are NOT lost
6. ✅ **Concurrent Events** - Multiple threads can emit events safely
7. ✅ **SSE Timeout** - Connections close after 30 seconds of inactivity
8. ✅ **Access Control** - Users can only access their own jobs' streams
9. ✅ **Data Integrity** - Events serialize correctly as JSON
10. ✅ **Queue Management** - Proper cleanup of event queues

## Test Classes

### 1. `TestHistoricalEventsOnSSEConnect` (2 tests)
Tests that the SSE endpoint returns historical events from the database when a client connects.

```python
test_historical_events_on_sse_connect()
test_sse_empty_when_no_events()
```

**Purpose**: Ensures events already in the database are sent to newly connected clients.

### 2. `TestNewEventsStreamLive` (1 test)
Tests that new events stream to clients in real-time after SSE connection.

```python
test_new_events_stream_live()
```

**Purpose**: Verifies the real-time streaming functionality works as events are emitted.

### 3. `TestEventOrder` (1 test)
Tests that events are delivered in chronological order.

```python
test_event_order()
```

**Purpose**: Ensures the UI can rely on event ordering for correct state management.

### 4. `TestEventPersistence` (3 tests)
Tests that events are immediately persisted to the database when emitted.

```python
test_event_persistence()
test_event_persistence_non_chat_events()
test_event_persistence_with_duration()
```

**Purpose**: Verifies the dispatcher's database persistence logic works correctly.

### 5. `TestRaceCondition` (3 tests)
**⚠️ CORE TESTS** - Tests the race condition bug we've been debugging:

```python
test_race_condition_events_before_connect()     # Main race condition test
test_race_condition_mixed_historical_and_live()  # Historical + live events
test_concurrent_event_emission()                 # Thread safety
```

**Purpose**: Ensures events emitted before SSE connection are NOT lost. This is the critical fix that prevents the UI from missing early events.

### 6. `TestSSETimeout` (2 tests)
Tests SSE connection timeout and proper HTTP headers.

```python
test_sse_timeout_after_inactivity()
test_sse_proper_headers()
```

**Purpose**: Verifies SSE connections close after 30 seconds of inactivity, preventing zombie connections.

### 7. `TestSSEAccessControl` (2 tests)
Tests authentication and authorization for the SSE endpoint.

```python
test_sse_requires_auth()
test_sse_denies_access_to_other_users_job()
```

**Purpose**: Ensures users cannot access SSE streams for other users' jobs.

### 8. `TestEventQueueManagement` (2 tests)
Tests event queue lifecycle (creation and cleanup).

```python
test_event_queue_created_on_sse_connect()
test_event_queue_cleanup_after_sse_disconnect()
```

**Purpose**: Prevents memory leaks from accumulating event queues.

### 9. `TestEventFormatAndDataIntegrity` (2 tests)
Tests SSE event JSON format and field completeness.

```python
test_sse_event_json_format()
test_sse_event_all_fields()
```

**Purpose**: Ensures the frontend receives properly formatted JSON events.

### 10. `TestSSEIntegrationWithDispatcher` (1 test)
Tests integration between event dispatcher and SSE queue system.

```python
test_dispatcher_emits_to_sse_queue()
```

**Purpose**: Verifies the core emit → persist → queue flow works correctly.

### 11. `TestLargeEventStreams` (1 test)
Tests SSE with large numbers of events.

```python
test_sse_with_many_events()
```

**Purpose**: Ensures performance with many events (stress test).

## Running the Tests

### Local Run (Host Machine)

```bash
cd /home/user/.openclaw/workspace/paper-reproducibility

# Run all SSE integration tests
python3 -m pytest tests/test_sse_integration.py -v

# Run specific test class
python3 -m pytest tests/test_sse_integration.py::TestRaceCondition -v

# Run specific test
python3 -m pytest tests/test_sse_integration.py::TestRaceCondition::test_race_condition_events_before_connect -v

# Run with detailed output
python3 -m pytest tests/test_sse_integration.py -vv --tb=short

# Run with print statements visible
python3 -m pytest tests/test_sse_integration.py -v -s
```

### Docker Container Run

```bash
# Run all tests in container
docker exec paper-reproducibility python3 -m pytest tests/test_sse_integration.py -v

# Run specific test class
docker exec paper-reproducibility python3 -m pytest tests/test_sse_integration.py::TestRaceCondition -v

# Run with coverage
docker exec paper-reproducibility python3 -m pytest tests/test_sse_integration.py --cov=blueprints --cov=services -v
```

### With Specific Markers (Future Enhancement)

```bash
# Run only race condition tests
pytest tests/test_sse_integration.py -m race_condition -v

# Run only access control tests  
pytest tests/test_sse_integration.py -m access_control -v
```

## Test Fixtures Used

The tests utilize fixtures from `conftest.py`:

- **`authenticated_user`** - Test client with authenticated session
- **`client`** - Flask test client
- **`app`** - Flask application instance
- **`peewee_test_db`** - In-memory Peewee database
- **`create_test_job`** - Factory to create test Job records
- **`create_test_event`** - Factory to create test Event records
- **`create_test_user`** - Factory to create test User records

## Key Test Scenarios

### The Race Condition (What We're Testing)

**Before Fix:**
```
[Time] Event A emitted → DB persisted → Queue (empty, no SSE client)
[Time] Event B emitted → DB persisted → Queue (empty, no SSE client)
[Time] Event C emitted → DB persisted → Queue (empty, no SSE client)
[Time] User connects SSE → only sees new events after this point
       ❌ Events A, B, C LOST!
```

**After Fix:**
```
[Time] Event A emitted → DB persisted → Queue (empty, no SSE client)
[Time] Event B emitted → DB persisted → Queue (empty, no SSE client)
[Time] Event C emitted → DB persisted → Queue (empty, no SSE client)
[Time] User connects SSE → SSE endpoint queries DB for all historical events
       → Sends A, B, C from DB
       → Then listens for new events
       ✅ All events received!
```

### Test: `test_race_condition_events_before_connect()`

This is the **critical test** that catches this bug:

1. Create a job
2. Emit 4 events **before** connecting to SSE
3. Connect to SSE and collect events
4. Verify all 4 events are received (not lost)

If this test passes, the race condition is fixed. If it fails, events are being lost.

## Expected Output

When all tests pass, you should see:

```
tests/test_sse_integration.py::TestHistoricalEventsOnSSEConnect::test_historical_events_on_sse_connect PASSED
tests/test_sse_integration.py::TestHistoricalEventsOnSSEConnect::test_sse_empty_when_no_events PASSED
tests/test_sse_integration.py::TestNewEventsStreamLive::test_new_events_stream_live PASSED
tests/test_sse_integration.py::TestEventOrder::test_event_order PASSED
tests/test_sse_integration.py::TestEventPersistence::test_event_persistence PASSED
tests/test_sse_integration.py::TestEventPersistence::test_event_persistence_non_chat_events PASSED
tests/test_sse_integration.py::TestEventPersistence::test_event_persistence_with_duration PASSED
tests/test_sse_integration.py::TestRaceCondition::test_race_condition_events_before_connect PASSED ⭐
tests/test_sse_integration.py::TestRaceCondition::test_race_condition_mixed_historical_and_live PASSED
tests/test_sse_integration.py::TestRaceCondition::test_concurrent_event_emission PASSED
tests/test_sse_integration.py::TestSSETimeout::test_sse_timeout_after_inactivity PASSED
tests/test_sse_integration.py::TestSSETimeout::test_sse_proper_headers PASSED
tests/test_sse_integration.py::TestSSEAccessControl::test_sse_requires_auth PASSED
tests/test_sse_integration.py::TestSSEAccessControl::test_sse_denies_access_to_other_users_job PASSED
tests/test_sse_integration.py::TestEventQueueManagement::test_event_queue_created_on_sse_connect PASSED
tests/test_sse_integration.py::TestEventQueueManagement::test_event_queue_cleanup_after_sse_disconnect PASSED
tests/test_sse_integration.py::TestEventFormatAndDataIntegrity::test_sse_event_json_format PASSED
tests/test_sse_integration.py::TestEventFormatAndDataIntegrity::test_sse_event_all_fields PASSED
tests/test_sse_integration.py::TestSSEIntegrationWithDispatcher::test_dispatcher_emits_to_sse_queue PASSED
tests/test_sse_integration.py::TestLargeEventStreams::test_sse_with_many_events PASSED

==================== 20 passed in X.XXs ====================
```

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError: No module named 'blueprints'`:

```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 -m pytest tests/test_sse_integration.py -v
```

### Database Errors

If you get database-related errors:

1. Ensure conftest.py fixtures are working:
   ```bash
   python3 -m pytest tests/test_app.py::TestDatabase -v
   ```

2. Check permissions on test database:
   ```bash
   ls -la /tmp/*.db
   ```

### Permission Errors

If you get permission errors on `__pycache__`:

```bash
# Remove pytest cache
rm -rf tests/__pycache__ .pytest_cache
# Re-run tests
python3 -m pytest tests/test_sse_integration.py -v
```

### Timeout Issues

If tests timeout (especially `test_race_condition_events_before_connect`):

1. Increase pytest timeout:
   ```bash
   pytest tests/test_sse_integration.py -v --timeout=30
   ```

2. Run just that test in isolation:
   ```bash
   pytest tests/test_sse_integration.py::TestRaceCondition::test_race_condition_events_before_connect -v -s
   ```

## Implementation Details

### What the Tests Mock

To avoid real processing, the tests:

- ✅ Use in-memory test database (via conftest.py)
- ✅ Mock LLM provider (not used in SSE tests)
- ✅ Mock Docker service (not used in SSE tests)
- ✅ Use real Flask test client (for authentic HTTP behavior)
- ✅ Use real Peewee ORM (to test actual DB persistence)

### What the Tests DON'T Mock

- ❌ Event emission (real emit_event() function)
- ❌ Event dispatcher (real EventDispatcher)
- ❌ Database persistence (real SQLite operations)
- ❌ SSE endpoint (real /events/<job_id> route)

This approach catches real bugs while avoiding external dependencies.

### Threading in Tests

Several tests use threading to simulate concurrent event emission:

```python
def test_concurrent_event_emission(self, app, create_test_job):
    # Multiple threads emit events simultaneously
    threads = [
        threading.Thread(target=emit_from_thread, args=(i,))
        for i in range(3)
    ]
```

This tests the thread-safety of:
- EventDispatcher.emit()
- Event queue locking
- Database transaction handling

## Performance Characteristics

Expected test duration:

- **Total suite**: ~5-10 seconds
- **Race condition tests**: ~2 seconds (most critical)
- **Timeout tests**: ~3 seconds (includes sleep delays)
- **Concurrent emission**: ~1 second

## Extending the Tests

To add new tests:

1. Add a test method to an existing class or create a new `TestXXX` class
2. Use the fixtures from conftest.py
3. Follow the existing pattern:

```python
def test_my_new_sse_feature(self, authenticated_user, create_test_job, create_test_event):
    """Test description."""
    job = create_test_job(job_id="test_job_new", status="processing")
    
    # Setup
    create_test_event("test_job_new", "step_1", "message")
    
    # Action
    response = authenticated_user.get('/events/test_job_new')
    
    # Assert
    assert response.status_code == 200
```

4. Run the test:
   ```bash
   pytest tests/test_sse_integration.py::TestNewClass::test_my_new_sse_feature -v
   ```

## CI/CD Integration

For GitHub Actions or other CI systems:

```yaml
- name: Run SSE Integration Tests
  run: |
    cd paper-reproducibility
    python3 -m pytest tests/test_sse_integration.py -v --tb=short
```

## Related Documentation

- **SSE Implementation**: `/blueprints/jobs.py` (events endpoint)
- **Event Dispatcher**: `/services/event_dispatcher.py`
- **Event Models**: `/models/events.py`
- **Database Models**: `/models/database.py`
- **Test Configuration**: `/tests/conftest.py`

## Questions?

If tests fail, check:

1. Are all dependencies installed? `pip install -r requirements.txt`
2. Is the database initialized? (conftest.py handles this)
3. Are there import path issues? (check PYTHONPATH)
4. Are there permission issues? (check file permissions)

## Summary

This test suite ensures the Paper Reproducibility Checker's real-time event streaming system:

✅ Never loses events (even if SSE connects after events are emitted)  
✅ Streams events in the correct order  
✅ Persists events immediately to the database  
✅ Handles concurrent event emission safely  
✅ Properly manages event queues and prevents memory leaks  
✅ Enforces access control  
✅ Returns properly formatted JSON  

**The critical test is `test_race_condition_events_before_connect()` which verifies the main bug fix.**
