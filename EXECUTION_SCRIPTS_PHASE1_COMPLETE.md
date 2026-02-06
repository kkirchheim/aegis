# Execution Scripts Phase 1 - Complete Implementation

## Status: ✅ BACKEND COMPLETE - All 13 Tests Passing

Phase 1 implements the backend infrastructure for execution scripts. The agent-side implementation remains (see "Next Steps").

---

## What Was Implemented

### 1. Data Models

**ExecutionScript** (script_hash is primary key, not UUID):
```python
script_hash: CharField(64)      # SHA256 hex - stable identifier
script_text: TextField()        # Full script with shebang
name: CharField()              # "Check README"
created_at: DateTimeField()
created_by: ForeignKeyField(User, null=True)
```

**ExecutionScriptResult**:
```python
id: UUIDField()                # Unique result ID
job: ForeignKeyField(Job)      # Which job
script_hash: CharField(64)     # Reference to script
exit_code: IntegerField()      # 0, 1, 2, or any code
stdout: TextField()            # Script output
stderr: TextField()            # Script errors
duration_ms: IntegerField()    # Execution time
created_at: DateTimeField()
```

### 2. Backend Utilities

**utils/script_utils.py**:
```python
hash_script(text)              # SHA256 hash of script
get_or_create_script(name, text, user_id)  # Idempotent creation
seed_default_scripts()         # Populate DEFAULT_SCRIPTS

DEFAULT_SCRIPTS = {
    "check_readme": "#!/bin/bash\ntest -f README.md && exit 0 || exit 1"
}
```

### 3. API Endpoints

**POST /agent/script_result**:
- Agent calls this to report script execution
- Input: `{job_id, script_hash, exit_code, stdout, stderr, duration_ms}`
- Validates job & script exist
- Stores result in database
- Emits event for live display
- Response: `{"ok": true}`

**GET /api/job/<job_id>/script_results**:
- Retrieve all script results for a job
- Auth required (session cookie)
- Returns: `{results: [...], total: N}`

### 4. Container Integration

**docker_service.py**:
- Load all ExecutionScript records
- Serialize as JSON: `{script_hash: {name, script_text}}`
- Pass via `SCRIPTS` environment variable to container

Agent receives:
```json
{
  "a1b2c3d4...": {
    "name": "Check README",
    "script_text": "#!/bin/bash\ntest -f README.md && exit 0 || exit 1"
  }
}
```

### 5. Tests (13 Total, All Passing)

✅ `test_hash_script_stable` - SHA256 is deterministic
✅ `test_hash_script_different_for_different_input` - Different scripts, different hashes
✅ `test_seed_default_scripts` - Creates hardcoded README check
✅ `test_seed_default_scripts_idempotent` - Safe to call multiple times
✅ `test_get_or_create_script_creates_new` - Creates on first call
✅ `test_get_or_create_script_returns_existing` - Returns existing on subsequent calls
✅ `test_script_result_storage` - Results persist to database
✅ `test_script_result_retrieval_by_job` - Can query results for a job
✅ `test_readme_check_script` - MVP script exists and is correct
✅ `test_api_endpoint_script_result` - Agent endpoint works
✅ `test_api_endpoint_invalid_job` - Rejects invalid jobs
✅ `test_api_endpoint_invalid_script_hash` - Rejects invalid scripts
✅ `test_get_script_results_endpoint` - Results endpoint exists

---

## Current Architecture

```
┌─────────────────────────────────────────────┐
│ Backend Server                              │
├─────────────────────────────────────────────┤
│ - ExecutionScript table (scripts)           │
│ - ExecutionScriptResult table (results)     │
│ - POST /agent/script_result (agent reports) │
│ - GET /api/job/<id>/script_results (UI)     │
│ - seed_default_scripts() at startup         │
└─────────────────────────────────────────────┘
          ↑                         ↓
   SCRIPTS env var          Results (events)
          ↓                         ↑
┌─────────────────────────────────────────────┐
│ Docker Container (Agent)                    │
├─────────────────────────────────────────────┤
│ Env: SCRIPTS={hash: {name, script_text}}    │
│                                             │
│ Agent must:                                 │
│ 1. Load SCRIPTS from env                    │
│ 2. Write /scripts/{hash}                    │
│ 3. chmod +x /scripts/{hash}                 │
│ 4. Execute: /scripts/{hash}                 │
│ 5. Capture: stdout, stderr, exit_code      │
│ 6. POST /agent/script_result                │
└─────────────────────────────────────────────┘
```

---

## Next Steps: Agent Implementation

The agent (running in Docker container) must implement:

### 1. Load Scripts from Environment

```python
import json
import os

scripts_json = os.getenv('SCRIPTS', '{}')
scripts = json.loads(scripts_json)

# scripts = {
#   "a1b2c3d4...": {
#     "name": "Check README",
#     "script_text": "#!/bin/bash\ntest -f README.md && exit 0 || exit 1"
#   }
# }
```

### 2. Write Scripts to Filesystem

```python
import os

os.makedirs('/scripts', exist_ok=True)

for script_hash, script_data in scripts.items():
    script_path = f'/scripts/{script_hash}'
    with open(script_path, 'w') as f:
        f.write(script_data['script_text'])
```

### 3. Make Executable and Set Working Directory

```python
import os

for script_hash in scripts.keys():
    script_path = f'/scripts/{script_hash}'
    os.chmod(script_path, 0o755)
```

### 4. Execute Scripts

```python
import subprocess
import time

for script_hash, script_data in scripts.items():
    script_path = f'/scripts/{script_hash}'
    
    start_time = time.time()
    try:
        result = subprocess.run(
            [script_path],
            capture_output=True,
            timeout=300,
            text=True,
            cwd='/workspace/repo'  # Run in repo directory
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Report result
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = "Script timeout after 5 minutes"
        duration_ms = 5 * 60 * 1000
    
    except Exception as e:
        exit_code = 127
        stdout = ""
        stderr = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
```

### 5. Report Result to Backend

```python
import requests

payload = {
    'job_id': os.getenv('JOB_ID'),
    'script_hash': script_hash,
    'exit_code': exit_code,
    'stdout': stdout,
    'stderr': stderr,
    'duration_ms': duration_ms
}

backend_url = os.getenv('BACKEND_URL')
response = requests.post(
    f"{backend_url}/agent/script_result",
    json=payload
)
```

### 6. Integration Point in Agent Loop

Scripts should run **after git clone** but **before the Claude decision loop**:

```python
async def main():
    # Clone repo
    git_clone(repo_url)
    
    # Run scripts (Phase 1 MVP)
    await run_scripts()
    
    # Then start Claude decision loop
    await agent_loop()

async def run_scripts():
    """Execute all scripts and report results."""
    scripts = json.loads(os.getenv('SCRIPTS', '{}'))
    
    os.makedirs('/scripts', exist_ok=True)
    
    for script_hash, script_data in scripts.items():
        # Write, chmod, execute, report
        ...
```

---

## Files Created/Modified

### New Files
- `models/execution_script.py` - Data models
- `utils/script_utils.py` - Hash, create, seed utilities
- `tests/test_execution_scripts_phase1.py` - 13 comprehensive tests
- `migrations/006_add_execution_scripts.py` - Migration (not used, auto-create enabled)

### Modified Files
- `blueprints/api.py` - Added 2 endpoints + imports
- `services/docker_service.py` - Pass SCRIPTS env var
- `app.py` - Call seed_default_scripts() at startup
- `models/database.py` - Add models to init_db()

### Documentation
- `EXECUTION_SCRIPTS_DESIGN_V3.md` - Final design (this implementation)
- `EXECUTION_SCRIPTS_PHASE1_COMPLETE.md` - This file

---

## How to Use (End-to-End)

### For Backend (Fully Implemented)

1. Scripts are seeded on app startup:
   ```
   seed_default_scripts() → ExecutionScript table populated
   ```

2. When agent container starts:
   ```
   docker_service.py reads ExecutionScript records
   Serializes as JSON
   Passes via SCRIPTS environment variable
   ```

3. Agent reports results:
   ```
   POST /agent/script_result
   → Stored in ExecutionScriptResult table
   → Event emitted for live display
   ```

4. UI retrieves results:
   ```
   GET /api/job/<id>/script_results
   → Returns all scripts and their results
   ```

### For Agent (To Implement)

1. Read environment: `os.getenv('SCRIPTS')`
2. Write to /scripts/{hash}
3. Execute each script
4. POST result to /agent/script_result

---

## Testing (Already Done)

Run all Phase 1 tests:
```bash
docker-compose exec app python3 -m pytest tests/test_execution_scripts_phase1.py -v
```

Expected output:
```
13 passed in 4.55s
```

---

## Limitations & Future Work

### Phase 1 Scope
- ✅ Backend infrastructure
- ✅ Hardcoded README check
- ✅ API endpoints
- ✅ Database storage
- ❌ Agent-side execution (next phase)
- ❌ UI display (after agent works)

### Phase 2 (After Agent Works)
- Run scripts before Claude loop (after_clone)
- Frontend display in job detail page
- More built-in scripts (requirements.txt, etc.)

### Phase 3+ (Future)
- User-provided custom scripts
- Script scheduling (after_install, after_code phases)
- Script management UI

---

## Debug/Verify

### Check backend is ready:
```bash
# Verify models
docker-compose exec app python3 -c "from models.execution_script import *; print('✓')"

# Check default scripts seeded
docker-compose exec app python3 -c "from models.execution_script import ExecutionScript; scripts = ExecutionScript.select(); print(f'{len(scripts)} scripts seeded')"

# Check API endpoint
curl -X POST http://localhost:5000/api/agent/script_result \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","script_hash":"test","exit_code":0}'
  # Should return 404 (invalid job) or 200 (if test job exists)
```

---

## Summary

✅ Phase 1 complete: Backend ready for agent integration
✅ 13 tests passing: All infrastructure validated
❌ Phase 2 needed: Agent must implement script execution

The system is **production-ready for backend**, waiting on **agent implementation** to complete the feature.
