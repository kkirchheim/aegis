# Execution Scripts - Simple Implementation Plan (V3)

## Core Simplifications

1. **No shebang parsing** - Scripts stored as-is with shebang in first line
2. **File-based execution** - Write to container filesystem, execute directly
3. **Hash-based identification** - Script hash = stable identifier (not UUID)
4. **Simple reporting** - Agent reports: `{script_hash, exit_code}`
5. **Phase 1 MVP** - Single hardcoded "README exists" check

---

## Phase 1: MVP (Just README Check)

### Hardcoded Script

```bash
#!/bin/bash
test -f README.md && exit 0 || exit 1
```

**Hash**: `sha256("#!/bin/bash\ntest -f README.md && exit 0 || exit 1")`

### Data Model (Minimal)

```python
class ExecutionScript(BaseModel):
    """User-provided script."""
    script_hash = CharField(primary_key=True)  # SHA256 of script_text
    script_text = TextField()                   # Full script with shebang
    name = CharField()                          # User-friendly name
    created_at = DateTimeField()
    created_by = ForeignKeyField(User, null=True)

class ExecutionScriptResult(BaseModel):
    """Result of running a script."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)
    script_hash = CharField()                   # Reference to script
    exit_code = IntegerField()                  # 0, 1, 2, or any other code
    stdout = TextField(null=True)
    stderr = TextField(null=True)
    duration_ms = IntegerField()
    created_at = DateTimeField()
```

### Database Migration

```sql
CREATE TABLE execution_script (
    script_hash VARCHAR(64) PRIMARY KEY,  -- SHA256 hex
    script_text TEXT NOT NULL,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES user(id)
);

CREATE TABLE execution_script_result (
    id UUID PRIMARY KEY,
    job_id VARCHAR REFERENCES job(id),
    script_hash VARCHAR(64) REFERENCES execution_script(script_hash),
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Backend Implementation

### 1. Hash Utility

```python
# utils/script_utils.py

import hashlib

def hash_script(script_text: str) -> str:
    """Generate stable hash for script."""
    return hashlib.sha256(script_text.encode()).hexdigest()

def get_or_create_script(name: str, script_text: str, user_id: int):
    """Get existing script or create new one."""
    script_hash = hash_script(script_text)
    
    try:
        script = ExecutionScript.get_by_id(script_hash)
        return script
    except:
        # Create new script
        script = ExecutionScript.create(
            script_hash=script_hash,
            script_text=script_text,
            name=name,
            created_by=user_id
        )
        return script
```

### 2. Seed Default Scripts

```python
# At app startup

DEFAULT_SCRIPTS = {
    "check_readme": """#!/bin/bash
test -f README.md && exit 0 || exit 1
""",
    # More scripts added in Phase 2+
}

def seed_default_scripts():
    """Create default scripts on first run."""
    from utils.script_utils import hash_script
    
    for name, script_text in DEFAULT_SCRIPTS.items():
        script_hash = hash_script(script_text)
        
        try:
            ExecutionScript.get_by_id(script_hash)
        except:
            ExecutionScript.create(
                script_hash=script_hash,
                script_text=script_text,
                name=name,
                created_by=None  # System script
            )
```

### 3. Pass Scripts to Container

```python
# In docker_service.py spawn_agent_container()

def spawn_agent_container(job_id, repo_url, config=None, ...):
    """Spawn agent container."""
    
    # Get all scripts (for now, just default ones)
    scripts = ExecutionScript.select()
    
    # Create scripts directory mapping
    scripts_data = {}
    for script in scripts:
        scripts_data[script.script_hash] = {
            "script_text": script.script_text,
            "name": script.name
        }
    
    # Pass to container
    container_kwargs["environment"]["SCRIPTS"] = json.dumps(scripts_data)
    
    # When container starts, agent will:
    # 1. Read SCRIPTS env var
    # 2. Write each script to /scripts/{hash}
    # 3. chmod +x /scripts/{hash}
    # 4. Execute when needed
```

### 4. Backend Endpoint for Script Results

```python
# In blueprints/api.py

@api_bp.route("/agent/script_result", methods=["POST"])
@use_kwargs({
    "job_id": fields.Str(required=True),
    "script_hash": fields.Str(required=True),
    "exit_code": fields.Int(required=True),
    "stdout": fields.Str(required=False, missing=""),
    "stderr": fields.Str(required=False, missing=""),
    "duration_ms": fields.Int(required=False, missing=0),
}, location="json")
def agent_script_result(job_id, script_hash, exit_code, stdout, stderr, duration_ms):
    """Agent reports script execution result."""
    
    # Validate job
    try:
        job = Job.get_by_id(job_id)
    except:
        return {"error": "Invalid job_id"}, 404
    
    # Validate script exists
    try:
        script = ExecutionScript.get_by_id(script_hash)
    except:
        return {"error": "Invalid script_hash"}, 404
    
    # Store result
    result = ExecutionScriptResult.create(
        job=job,
        script_hash=script_hash,
        exit_code=exit_code,
        stdout=stdout[:5000],  # Limit size
        stderr=stderr[:5000],
        duration_ms=duration_ms
    )
    
    # Emit event
    from blueprints.jobs import emit_event
    emit_event(job_id, {
        'event': 'script_executed',
        'script_name': script.name,
        'script_hash': script_hash,
        'exit_code': exit_code,
        'stdout': stdout[:500] if stdout else '',
        'duration_ms': duration_ms
    })
    
    return {"ok": True}
```

---

## Agent-Side Implementation (in Container)

```python
# In agent.py (running in Docker container)

import json
import os
import subprocess
import time

class Agent:
    def __init__(self):
        self.job_id = os.getenv('JOB_ID')
        self.repo_url = os.getenv('REPO_URL')
        self.backend_url = os.getenv('BACKEND_URL')
        self.scripts = {}  # Hash -> script_text
        
        # Load scripts from environment
        scripts_json = os.getenv('SCRIPTS', '{}')
        self.scripts = json.loads(scripts_json)
    
    async def run(self):
        """Main agent loop."""
        
        # Phase 1: Clone repo
        self.clone_repo()
        
        # Phase 1a: Run scripts (after clone)
        await self.run_scripts_phase()
        
        # Phase 2: Agent loop (existing Claude logic)
        await self.agent_loop()
    
    async def run_scripts_phase(self):
        """Execute all scripts and report results."""
        
        # Create scripts directory
        os.makedirs('/scripts', exist_ok=True)
        
        for script_hash, script_data in self.scripts.items():
            # Write script to file
            script_path = f'/scripts/{script_hash}'
            with open(script_path, 'w') as f:
                f.write(script_data['script_text'])
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            # Execute script
            result = self.execute_script(script_path, script_hash)
            
            # Report back to backend
            await self.report_script_result(result)
    
    def execute_script(self, script_path: str, script_hash: str) -> dict:
        """Execute a script and capture result."""
        
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
            
            return {
                'script_hash': script_hash,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'duration_ms': duration_ms
            }
        
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                'script_hash': script_hash,
                'exit_code': 124,  # Standard timeout exit code
                'stdout': '',
                'stderr': 'Script timeout after 5 minutes',
                'duration_ms': duration_ms
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                'script_hash': script_hash,
                'exit_code': 127,  # Standard "command not found" code
                'stdout': '',
                'stderr': str(e),
                'duration_ms': duration_ms
            }
    
    async def report_script_result(self, result: dict):
        """Report script result back to backend."""
        
        import aiohttp
        
        url = f"{self.backend_url}/agent/script_result"
        payload = {
            'job_id': self.job_id,
            'script_hash': result['script_hash'],
            'exit_code': result['exit_code'],
            'stdout': result['stdout'],
            'stderr': result['stderr'],
            'duration_ms': result['duration_ms']
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"Error reporting script result: {resp.status}")
```

---

## Frontend

### Live Event Display

User sees real-time output:

```
[14:31:20] ─────────────────────────────────────────
[14:31:20] Script: "Check README"
[14:31:20] Status: ✓ SUCCESS (exit code 0)
[14:31:20] Duration: 45ms
[14:31:20] ─────────────────────────────────────────
```

### Job Detail - Script Results Section

```html
<section class="card bg-base-100 shadow-lg">
  <div class="card-body">
    <h2 class="card-title">Script Results</h2>
    
    <div id="scriptResults" class="space-y-3">
      <!-- Rendered by JavaScript from API -->
    </div>
  </div>
</section>
```

```javascript
// Fetch and display script results
async function loadScriptResults(jobId) {
    const response = await fetch(`/api/job/${jobId}/script_results`);
    const data = await response.json();
    
    const container = document.getElementById('scriptResults');
    
    for (const result of data.results) {
        const statusIcon = result.exit_code === 0 ? '✓' : '✗';
        const statusColor = result.exit_code === 0 ? 'badge-success' : 'badge-error';
        
        const html = `
            <div class="card card-compact bg-base-200">
                <div class="card-body p-3">
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="text-lg">${statusIcon}</span>
                            <span class="font-semibold">${result.script_name}</span>
                        </div>
                        <span class="badge ${statusColor}">exit ${result.exit_code}</span>
                    </div>
                    ${result.stdout ? `<pre class="text-xs mt-2 bg-base-300 p-2">${result.stdout}</pre>` : ''}
                    <span class="text-xs text-gray-500">${result.duration_ms}ms</span>
                </div>
            </div>
        `;
        
        container.innerHTML += html;
    }
}
```

### API Endpoint for Results

```python
@api_bp.route("/job/<job_id>/script_results", methods=["GET"])
def get_script_results(job_id):
    """Get all script results for a job."""
    
    results = (
        ExecutionScriptResult
        .select()
        .join(ExecutionScript)
        .where(ExecutionScriptResult.job == job_id)
        .order_by(ExecutionScriptResult.created_at.asc())
    )
    
    return {
        "results": [
            {
                "script_name": r.script.name,
                "script_hash": r.script_hash,
                "exit_code": r.exit_code,
                "stdout": r.stdout or '',
                "stderr": r.stderr or '',
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat()
            }
            for r in results
        ]
    }
```

---

## Integration with Pipeline Orchestrator

**No changes needed**. Scripts are passed to agent via environment variable.

```python
# In docker_service.py - already part of container creation

container_kwargs["environment"]["SCRIPTS"] = json.dumps(scripts_data)
```

Agent handles everything:
1. Loads SCRIPTS from environment
2. Writes to /scripts/{hash}
3. Executes
4. Reports via `/agent/script_result`

---

## Phase 1 Implementation Steps

### Step 1: Models (30 min)
- [ ] Create ExecutionScript model (script_hash as PK, script_text, name)
- [ ] Create ExecutionScriptResult model (references script_hash)
- [ ] Create migration

### Step 2: Utilities (20 min)
- [ ] Implement hash_script()
- [ ] Implement get_or_create_script()
- [ ] Implement seed_default_scripts()

### Step 3: Backend (30 min)
- [ ] Add `/agent/script_result` endpoint
- [ ] Modify docker_service.py to pass SCRIPTS env var
- [ ] Add `/api/job/<id>/script_results` endpoint
- [ ] Add seed_default_scripts() call in app startup

### Step 4: Agent (30 min)
- [ ] Read SCRIPTS from environment
- [ ] Write scripts to /scripts/{hash}
- [ ] chmod +x
- [ ] Execute and capture output
- [ ] POST to `/agent/script_result`

### Step 5: Frontend (30 min)
- [ ] Add script results section to job detail page
- [ ] Display results in table format
- [ ] Handle exit codes (color coding)

### Step 6: Testing (30 min)
- [ ] Unit test: hash_script()
- [ ] Integration test: script execution
- [ ] E2E test: script → result → UI display
- [ ] Test with hardcoded README check

**Total: ~3 hours for MVP**

---

## Hardcoded README Script (Phase 1)

```python
DEFAULT_SCRIPTS = {
    "check_readme": """#!/bin/bash
test -f README.md && exit 0 || exit 1
"""
}
```

Result when run:
- `exit 0` if README.md exists
- `exit 1` if not found

Displays in UI:
```
✓ Check README (exit code 0)
```

---

## Example: Extending to Phase 2

Once Phase 1 works, add more scripts:

```python
DEFAULT_SCRIPTS = {
    "check_readme": """#!/bin/bash
test -f README.md && exit 0 || exit 1
""",
    
    "check_requirements": """#!/bin/bash
test -f requirements.txt && exit 0 || exit 1
""",
    
    "check_main_script": """#!/bin/bash
test -f main.py || test -f run.py || test -f train.py && exit 0 || exit 1
""",
}
```

All scripts:
1. Write to /scripts/{hash}
2. Execute in parallel (no ordering)
3. Report individually
4. Display in UI

---

## Data Flow Summary

```
┌──────────────────────────────────┐
│ Phase 1: MVP (Just README check) │
└──────────────────────────────────┘

User uploads paper
  ↓
Backend seeded with DEFAULT_SCRIPTS (one hardcoded script)
  ↓
Stage 2: Agent spawned in container
  ↓
Agent receives SCRIPTS env var:
  {
    "a1b2c3d4...": {
      "name": "Check README",
      "script_text": "#!/bin/bash\ntest -f README.md && exit 0 || exit 1"
    }
  }
  ↓
Agent:
  1. mkdir -p /scripts
  2. Write to /scripts/a1b2c3d4...
  3. chmod +x /scripts/a1b2c3d4...
  4. Execute: /scripts/a1b2c3d4...
  5. Capture: exit_code=0, stdout="", stderr=""
  6. POST to /agent/script_result
  ↓
Backend:
  1. Validate job & script
  2. Store ExecutionScriptResult
  3. Emit event (for live display)
  ↓
User sees:
  [Script: "Check README"] [✓ SUCCESS] [exit 0]
```

---

## Why This Works

✅ **No shebang parsing** - Scripts stored as-is, executed directly by shell
✅ **Hash-based** - Same script text = same hash = same identifier
✅ **Simple** - Write file, chmod, execute, report
✅ **Deterministic** - No LLM involvement, same result every time
✅ **Extensible** - Phase 2 adds more scripts to DEFAULT_SCRIPTS
✅ **Real-time** - Events stream to user as scripts execute
✅ **Minimal code** - ~200 lines for Phase 1 MVP

---

## Next Phases (Future)

**Phase 2**: User-provided scripts (upload via UI)
- API endpoint: POST /scripts to create custom script
- UI: Upload textarea with script text
- Store in database, hash automatically

**Phase 3**: Script scheduling
- run_before_agent: Scripts before Claude loop
- run_after_agent: Scripts after Claude loop
- run_before_code: Scripts before main code execution
- run_after_code: Scripts after main code execution

**Phase 4**: Script management UI
- View, edit, delete scripts
- Enable/disable per job
- Share scripts across jobs (by hash)
