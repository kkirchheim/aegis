# Debugging Guide

## The Problem

When the agent gets "Could not parse Claude response, aborting", we need to see exactly what Claude is returning to understand why JSON parsing is failing.

## What's Now Logged

With the latest deployment, when `/api/agent/think` is called, the backend logs:

### Full Claude Response
```
[job-id] === Claude Response (Full, 523 chars) ===
[job-id] {
  "action": "read_file",
  "target": "README.md",
  "reasoning": "..."
}
[job-id] === End Claude Response ===
```

### Parsing Attempts
Each parsing method is logged:
```
[job-id] ✓ Parsed JSON directly (Method 1)
```

Or if it fails:
```
[job-id] ✗ Direct JSON parsing failed: Expecting value: line 1 column 1
[job-id] ✗ Method 2 failed: list index out of range
[job-id] ✗ ALL PARSING METHODS FAILED!
[job-id] Response text: {truncated}
[job-id] Response length: 523
[job-id] Response contains '{': True
[job-id] Response contains '```': False
```

## How to Debug

### 1. Check Docker Logs
```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
docker-compose logs -f | grep "Claude Response"
```

This shows:
- The full response from Claude (not truncated!)
- Which parsing method succeeded (or all failed)
- Exact error messages from each attempt
- Response length and characteristics

### 2. Look for Markers
Search for these in logs:

**Good:** ✓ (means parsing succeeded)
```
[job-id] ✓ Parsed JSON directly (Method 1)
```

**Bad:** ✗ (means parsing failed)
```
[job-id] ✗ Direct JSON parsing failed: ...
[job-id] ✗ ALL PARSING METHODS FAILED!
```

### 3. Understand the Four Parsing Methods

| # | Method | Handles | Failure Reason |
|---|--------|---------|----------------|
| 1 | Direct `json.loads()` | Valid JSON | Claude returned plain JSON with syntax error |
| 2 | Extract from ` ``` json ` | JSON in markdown code block | Claude wrapped response in wrong block type |
| 3 | Extract from ` ``` ` plain | JSON in plain code block | Claude wrapped in plain ` ``` ` instead of ` ```json ` |
| 4 | Find JSON substring | Partial/truncated JSON | Claude response was cut off mid-JSON or text around JSON |

### 4. Common Issues & Solutions

**Issue: Method 1 fails with syntax error**
```
✗ Direct JSON parsing failed: Expecting value: line 5 column 3
```
→ Claude sent malformed JSON (missing comma, wrong quotes, etc.)
→ Check response for syntax errors
→ May need better Claude prompt

**Issue: All methods fail, response length < 100 chars**
```
✗ ALL PARSING METHODS FAILED!
Response length: 42
```
→ Claude returned something tiny (error message, apology, etc.)
→ Check if Claude ran out of tokens
→ May need to reduce prompt size

**Issue: Response has `{` but no valid JSON found**
```
Response contains '{': True
```
→ Claude started JSON but didn't finish
→ Check if response was truncated
→ May need to increase `max_tokens`

## Example: Real Debugging Session

### Scenario: "Could not parse Claude response, aborting"

**Step 1:** Look at logs
```
[ca2a9ad4] === Claude Response (Full, 237 chars) ===
[ca2a9ad4] I think the agent should read the README to understand the project structure.
[ca2a9ad4] === End Claude Response ===
```

**Problem:** Claude returned prose, not JSON!

**Step 2:** Check parsing attempts
```
[ca2a9ad4] ✗ Direct JSON parsing failed: Expecting value: line 1 column 1
[ca2a9ad4] ✗ Method 2 failed: list index out of range
[ca2a9ad4] ✗ ALL PARSING METHODS FAILED!
[ca2a9ad4] Response text: I think the agent should...
```

**Step 3:** Identify root cause
- Claude forgot to return JSON (format confusion)
- Prompt may not be clear enough
- Token limit too low for thinking

**Step 4:** Solution
- Improve Claude prompt (be more explicit)
- Add format reminders
- Check if response is truncated

## For Developers

### Adding Debug Logging to New Endpoints

When adding a new endpoint that parses JSON:

```python
@app.route("/api/new/endpoint", methods=["POST"])
def new_endpoint():
    data = request.json
    
    # Log the input for debugging
    app.logger.info(f"[{job_id}] === Input Data ===")
    app.logger.info(f"[{job_id}] {json.dumps(data, indent=2)}")
    app.logger.info(f"[{job_id}] === End Input ===")
    
    # Do work...
    
    # Log output
    app.logger.info(f"[{job_id}] === Output ===")
    app.logger.info(f"[{job_id}] {json.dumps(result, indent=2)}")
    
    return jsonify(result)
```

### Testing Malformed Responses

The test suite includes tests for:
- `test_detailed_logging_on_parse_failure` - Verifies logging works
- `test_malformed_responses` - Tests graceful failure

Run with:
```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
docker run --rm -v "$PWD:/app" -w /app python:3.10-slim bash -c \
  "pip install -q pytest flask requests docker anthropic pdfplumber python-dotenv && \
   python -m pytest tests/test_agent_api.py::TestDebugLogging -v"
```

## Real-Time Monitoring

Watch logs as the agent runs:

```bash
# Terminal 1: Watch backend logs
docker-compose logs -f paper-reproducibility | grep -E "Claude Response|Parsed|FAILED|✓|✗"

# Terminal 2: Upload PDF or trigger job
curl -X POST http://localhost:5000/upload -F "pdf=@paper.pdf"
```

This gives real-time visibility into what Claude is returning and how it's being parsed.
