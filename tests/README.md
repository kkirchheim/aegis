# Test Suite

## Quick Start

Run all tests:
```bash
cd ..
docker run --rm -v "$PWD:/app" -w /app python:3.10-slim bash -c \
  "pip install -q pytest flask requests docker anthropic pdfplumber python-dotenv && \
   python -m pytest tests/ -v"
```

## Files

- `test_agent_api.py` - Tests for agent backend API endpoints

## Test Patterns Used

### Edge Case Coverage

All tests cover:
- ✅ Happy path (normal inputs)
- ✅ Missing fields (robustness)
- ✅ None values (the bug we fixed!)
- ✅ Empty collections (edge cases)
- ✅ Very large inputs (stress tests)
- ✅ Special characters (escaping)

### Why This Matters

The bug we just fixed (`object of type 'NoneType' has no len()`) would have been caught immediately by these tests.

**Before fix:**
```
test_none_errors FAILED
Error in agent/think: object of type 'NoneType' has no len()
```

**After fix:**
```
test_none_errors PASSED ✓
```

## Contributing Tests

When you find a bug:
1. Write a test that reproduces it
2. Commit the failing test
3. Fix the code
4. Verify test passes
5. Push with both test + fix

This prevents regressions!
