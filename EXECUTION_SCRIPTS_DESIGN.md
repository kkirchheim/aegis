# Execution Scripts - Implementation Plan

## Overview

Users provide simple scripts that the **agent executes in the container** after cloning. Scripts use shebangs to specify interpreter, return three codes (0/1/2), and output is streamed back to the user in real-time.

```
User provides:          Agent in container:         Result to user:
┌──────────────┐       ┌──────────────────┐        ┌─────────────┐
│ #!/bash      │  →    │ Parse shebang    │   →    │ Live event  │
│ test -f ...  │       │ Execute script   │        │ "Script: OK"│
│ exit 0       │       │ Capture output   │        │ stdout: ... │
└──────────────┘       │ Return code      │        │ Code: 0     │
                       │ Send via event   │        └─────────────┘
                       └──────────────────┘
```

---

## Data Model

### 1. ExecutionScript Model

```python
class ExecutionScript(BaseModel):
    """User-provided execution script."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)
    
    # Script definition
    script_text = TextField()           # Full script with shebang
    name = CharField()                  # User-friendly name ("Check README")
    description = TextField(null=True)  # What does this check do?
    
    # Execution control
    run_order = IntegerField()          # Order to run scripts (1, 2, 3, ...)
    run_after_clone = BooleanField()    # Run immediately after git clone?
    run_after_install = BooleanField()  # Run after pip install?
    run_after_code = BooleanField()     # Run after main code executes?
    
    # Creation metadata
    created_at = DateTimeField()
    created_by = ForeignKeyField(User, null=True)  # null = admin default
```

### 2. ExecutionScriptResult Model

```python
class ExecutionScriptResult(BaseModel):
    """Result of running a script."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)
    script = ForeignKeyField(ExecutionScript)
    
    # Result data
    exit_code = IntegerField()          # 0: success, 1: undetermined, 2: failure
    stdout = TextField(null=True)       # Script output
    stderr = TextField(null=True)       # Script errors
    
    # Timing
    started_at = DateTimeField()
    ended_at = DateTimeField()
    duration_ms = IntegerField()
    
    # Metadata
    phase = CharField()                 # 'after_clone', 'after_install', 'after_code'
    created_at = DateTimeField()
```

### 3. Database Migration

```sql
CREATE TABLE execution_script (
    id UUID PRIMARY KEY,
    job_id VARCHAR REFERENCES job(id),
    script_text TEXT NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    run_order INTEGER DEFAULT 0,
    run_after_clone BOOLEAN DEFAULT FALSE,
    run_after_install BOOLEAN DEFAULT FALSE,
    run_after_code BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES user(id)
);

CREATE TABLE execution_script_result (
    id UUID PRIMARY KEY,
    job_id VARCHAR REFERENCES job(id),
    script_id UUID REFERENCES execution_script(id),
    exit_code INTEGER CHECK (exit_code IN (0, 1, 2)),
    stdout TEXT,
    stderr TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_ms INTEGER,
    phase VARCHAR CHECK (phase IN ('after_clone', 'after_install', 'after_code')),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Shebang Parsing

### How Shebangs Work

```python
def parse_shebang(script_text):
    """Extract interpreter from shebang line."""
    
    lines = script_text.split('\n')
    if not lines:
        raise ValueError("Script is empty")
    
    first_line = lines[0].strip()
    
    # Extract shebang
    if not first_line.startswith('#!'):
        raise ValueError("Script must start with shebang (e.g., #!bash, #!python)")
    
    interpreter = first_line[2:].strip()  # Remove '#!' and whitespace
    
    # Normalize common interpreters
    interpreter_map = {
        'bash': '/bin/bash',
        'sh': '/bin/sh',
        'python': 'python3',
        'python3': 'python3',
        'python2': 'python2',
        'node': 'node',
        'ruby': 'ruby',
        'perl': 'perl',
        'javascript': 'node',
    }
    
    cmd = interpreter_map.get(interpreter, interpreter)
    
    # Rest of script (without shebang)
    script_body = '\n'.join(lines[1:])
    
    return cmd, script_body


# Examples
parse_shebang("#!bash\necho hello")          # → ('/bin/bash', 'echo hello')
parse_shebang("#!python\nprint('hi')")       # → ('python3', "print('hi')")
parse_shebang("#!node\nconsole.log('hi')")   # → ('node', "console.log('hi')")
```

---

## Agent-Side Execution

The **agent running inside the container** receives scripts and executes them.

### Agent Receives Scripts

**From main controller (via job context)**:

```json
{
  "job_id": "abc123",
  "scripts": [
    {
      "id": "script-1",
      "name": "Check README",
      "script_text": "#!bash\ntest -f README.md && exit 0 || exit 1",
      "run_after_clone": true,
      "run_after_install": false,
      "run_after_code": false
    },
    {
      "id": "script-2", 
      "name": "Validate Requirements",
      "script_text": "#!python\nimport sys\nopen('requirements.txt').read()",
      "run_after_clone": true,
      "run_after_install": false,
      "run_after_code": false
    }
  ]
}
```

### Agent Execution Function

```python
# In agent.py (running inside container)

def execute_scripts(scripts, phase='after_clone'):
    """Execute all scripts for a given phase."""
    
    results = []
    
    # Filter scripts for this phase
    scripts_to_run = [
        s for s in scripts
        if phase == 'after_clone' and s.get('run_after_clone')
        or phase == 'after_install' and s.get('run_after_install')
        or phase == 'after_code' and s.get('run_after_code')
    ]
    
    # Sort by run order
    scripts_to_run.sort(key=lambda s: s.get('run_order', 0))
    
    for script_def in scripts_to_run:
        result = execute_single_script(script_def)
        results.append(result)
        
        # Send result back to controller via event
        emit_event({
            'event': 'script_executed',
            'script_id': script_def['id'],
            'script_name': script_def['name'],
            'exit_code': result['exit_code'],
            'stdout': result['stdout'],
            'stderr': result['stderr'],
            'duration_ms': result['duration_ms'],
            'phase': phase
        })
    
    return results


def execute_single_script(script_def):
    """Execute a single script and capture output."""
    
    import subprocess
    import time
    import tempfile
    
    script_text = script_def['script_text']
    script_id = script_def['id']
    
    try:
        # Parse shebang
        interpreter, script_body = parse_shebang(script_text)
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix=get_file_extension(interpreter)
        ) as f:
            f.write(script_body)
            temp_script = f.name
        
        # Make executable
        os.chmod(temp_script, 0o755)
        
        # Execute script
        start_time = time.time()
        
        result = subprocess.run(
            [interpreter, temp_script],
            capture_output=True,
            timeout=300,  # 5 minute timeout
            text=True
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Validate exit code
        if result.returncode not in [0, 1, 2]:
            # Script exit code not in valid range, treat as 2 (failure)
            exit_code = 2
        else:
            exit_code = result.returncode
        
        return {
            'script_id': script_id,
            'exit_code': exit_code,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration_ms': duration_ms,
            'success': result.returncode == 0
        }
    
    except subprocess.TimeoutExpired:
        return {
            'script_id': script_id,
            'exit_code': 2,  # Failure
            'stdout': '',
            'stderr': f'Script timeout after 5 minutes',
            'duration_ms': 5 * 60 * 1000,
            'success': False
        }
    
    except Exception as e:
        return {
            'script_id': script_id,
            'exit_code': 2,  # Failure
            'stdout': '',
            'stderr': f'Error executing script: {str(e)}',
            'duration_ms': 0,
            'success': False
        }
    
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_script)
        except:
            pass


def get_file_extension(interpreter):
    """Get file extension for temp file based on interpreter."""
    ext_map = {
        'bash': '.sh',
        'sh': '.sh',
        'python3': '.py',
        'python2': '.py',
        'python': '.py',
        'node': '.js',
        'ruby': '.rb',
        'perl': '.pl',
    }
    return ext_map.get(interpreter, '.txt')
```

### Agent Integration Points

```python
# In agent.py, add execution script calls

async def run_job(job_config):
    """Main job loop."""
    
    scripts = job_config.get('scripts', [])
    
    # Phase 1: After cloning repo
    print("Cloning repository...")
    git_clone(repo_url)
    
    execute_scripts(scripts, phase='after_clone')
    
    # Phase 2: After installing dependencies
    print("Installing dependencies...")
    install_dependencies()
    
    execute_scripts(scripts, phase='after_install')
    
    # Phase 3: Run the actual code
    print("Running code...")
    run_code()
    
    # Phase 4: After code execution
    execute_scripts(scripts, phase='after_code')
    
    print("Job complete")
```

---

## API Endpoints

### 1. Add Script to Job

```
POST /api/job/{job_id}/scripts

Body:
{
  "name": "Check README",
  "script_text": "#!bash\ntest -f README.md && exit 0 || exit 1",
  "run_after_clone": true,
  "run_after_install": false,
  "run_after_code": false,
  "run_order": 1
}

Response:
{
  "id": "script-uuid",
  "job_id": "job-uuid",
  "name": "Check README",
  "created_at": "2026-02-06T16:30:00Z"
}
```

### 2. List Scripts for Job

```
GET /api/job/{job_id}/scripts

Response:
{
  "scripts": [
    {
      "id": "script-1",
      "name": "Check README",
      "script_text": "#!bash\ntest -f README.md && exit 0 || exit 1",
      "run_after_clone": true,
      "run_order": 1
    }
  ],
  "total": 1
}
```

### 3. Get Script Results

```
GET /api/job/{job_id}/scripts/{script_id}/results

Response:
[
  {
    "id": "result-1",
    "script_id": "script-1",
    "exit_code": 0,
    "stdout": "README found",
    "stderr": "",
    "duration_ms": 45,
    "phase": "after_clone",
    "created_at": "2026-02-06T16:31:00Z"
  }
]
```

### 4. Delete Script

```
DELETE /api/job/{job_id}/scripts/{script_id}
```

---

## Frontend Integration

### 1. Script Upload UI (Job Detail Page)

```html
<section class="card bg-base-100 shadow-lg">
  <div class="card-body">
    <h2 class="card-title">Execution Scripts</h2>
    <p class="text-sm text-gray-600">
      Add scripts that run after cloning. Use shebangs: #!bash, #!python, #!node
    </p>
    
    <!-- Script Form -->
    <div class="form-control">
      <label class="label">
        <span class="label-text">Script Name</span>
      </label>
      <input type="text" id="scriptName" placeholder="Check README" 
             class="input input-bordered" />
    </div>
    
    <!-- Shebang & Content -->
    <div class="form-control">
      <label class="label">
        <span class="label-text">Script Content</span>
      </label>
      <textarea id="scriptContent" 
                placeholder="#!bash&#10;test -f README.md && exit 0 || exit 1"
                class="textarea textarea-bordered font-mono text-sm" rows="8"></textarea>
    </div>
    
    <!-- When to Run -->
    <div class="form-control">
      <label class="label">
        <span class="label-text">Run After</span>
      </label>
      <div class="space-y-2">
        <label class="label cursor-pointer">
          <input type="checkbox" id="runAfterClone" class="checkbox" checked />
          <span class="label-text">Clone</span>
        </label>
        <label class="label cursor-pointer">
          <input type="checkbox" id="runAfterInstall" class="checkbox" />
          <span class="label-text">Install Dependencies</span>
        </label>
        <label class="label cursor-pointer">
          <input type="checkbox" id="runAfterCode" class="checkbox" />
          <span class="label-text">Code Execution</span>
        </label>
      </div>
    </div>
    
    <button class="btn btn-primary" onclick="addScript()">Add Script</button>
  </div>
</section>
```

### 2. Live Script Execution Display

In the live events stream, display script results:

```
[14:31:20] ─────────────────────────────────────────
[14:31:20] Script: "Check README"
[14:31:20] Status: ✓ SUCCESS (exit code 0)
[14:31:20] Output:
[14:31:20]   README.md exists and is 1245 bytes
[14:31:20] Duration: 45ms
[14:31:20] ─────────────────────────────────────────

[14:31:21] Script: "Validate Python"
[14:31:21] Status: ✗ FAILURE (exit code 2)
[14:31:21] Error:
[14:31:21]   ImportError: No module named 'tensorflow'
[14:31:21] Duration: 234ms
[14:31:21] ─────────────────────────────────────────

[14:31:25] Script: "Check Results"
[14:31:25] Status: ⚠ UNDETERMINED (exit code 1)
[14:31:25] Output:
[14:31:25]   Could not parse output format
[14:31:25] Duration: 156ms
[14:31:25] ─────────────────────────────────────────
```

### 3. Results Summary

In the job detail page, show script results section:

```
Execution Scripts (after_clone)
├─ ✓ Check README (45ms)
│  └ "README.md exists and is 1245 bytes"
└─ ✓ Validate Python (234ms)
   └ "Python 3.10.5 OK"

Execution Scripts (after_code)
├─ ✓ Parse Results (156ms)
│  └ "accuracy: 0.9333"
└─ ✗ Verify Match (89ms)
   └ "accuracy mismatch: expected 0.93, got 0.9333"
```

---

## Adjustment to Pipeline Orchestrator

### Stage 2 Changes

```python
def _run_stage_2(self, job_id: str, config) -> bool:
    """Stage 2: Execute code from artifacts + user scripts."""
    
    try:
        self.logger(f"[{job_id}] >>> STAGE 2 STARTING")
        
        # Get execution scripts for this job
        scripts = get_execution_scripts(job_id)
        
        # Spawn container
        container = spawn_agent_container(
            job_id=job_id,
            repo_url=artifact_url,
            config=config,
            scripts=scripts,  # ← Pass scripts to agent
            emit_event=self.emit_event
        )
        
        # Agent will:
        # 1. Clone repo
        # 2. Execute scripts (after_clone phase)
        # 3. Install deps
        # 4. Execute scripts (after_install phase)
        # 5. Run code
        # 6. Execute scripts (after_code phase)
        # 7. Send results back via events
        
        self.emit_event(job_id, "stage_2_complete", "Code execution complete")
        return True
    
    except Exception as e:
        self.logger(f"[{job_id}] Stage 2 failed: {str(e)}")
        return False
```

### Event System Integration

Scripts emit events just like any other stage event:

```python
# In agent.py
def emit_event(event_data):
    """Send event to main controller."""
    requests.post(
        f"{CONTROLLER_URL}/api/job/{job_id}/events",
        json={
            'event': event_data['event'],
            'timestamp': datetime.now().isoformat(),
            'data': event_data
        }
    )

# Example events:
emit_event({
    'event': 'script_executed',
    'script_id': 'script-1',
    'script_name': 'Check README',
    'exit_code': 0,
    'stdout': 'README.md found, 1245 bytes',
    'stderr': '',
    'duration_ms': 45,
    'phase': 'after_clone'
})
```

---

## Database Schema Summary

```python
# Two new tables

ExecutionScript:
  - id (UUID)
  - job_id (FK)
  - script_text (TEXT)
  - name (VARCHAR)
  - description (TEXT)
  - run_after_clone (BOOL)
  - run_after_install (BOOL)
  - run_after_code (BOOL)
  - run_order (INT)
  - created_by (FK User)
  - created_at (TIMESTAMP)

ExecutionScriptResult:
  - id (UUID)
  - job_id (FK)
  - script_id (FK)
  - exit_code (INT: 0/1/2)
  - stdout (TEXT)
  - stderr (TEXT)
  - started_at (TIMESTAMP)
  - ended_at (TIMESTAMP)
  - duration_ms (INT)
  - phase (VARCHAR)
  - created_at (TIMESTAMP)
```

---

## Implementation Steps

### Step 1: Database & Models (1-2 hours)
- [ ] Create ExecutionScript model
- [ ] Create ExecutionScriptResult model
- [ ] Create migration
- [ ] Create repositories

### Step 2: Agent-Side Execution (2-3 hours)
- [ ] Implement parse_shebang()
- [ ] Implement execute_single_script()
- [ ] Implement execute_scripts() phase handler
- [ ] Integrate into agent job loop
- [ ] Emit events for each script result

### Step 3: API Endpoints (1-2 hours)
- [ ] POST /api/job/{id}/scripts (add script)
- [ ] GET /api/job/{id}/scripts (list scripts)
- [ ] GET /api/job/{id}/scripts/{sid}/results (get results)
- [ ] DELETE /api/job/{id}/scripts/{sid} (delete script)
- [ ] Validation (shebang check, max size, etc.)

### Step 4: Frontend (2-3 hours)
- [ ] Script upload form in job detail page
- [ ] Live event display for script output
- [ ] Results summary section
- [ ] Edit/delete script functionality

### Step 5: Testing (2-3 hours)
- [ ] Unit tests: parse_shebang()
- [ ] Integration tests: agent executes scripts
- [ ] E2E tests: script → event → UI display
- [ ] Edge cases: timeout, invalid shebang, large output

---

## Example Use Cases

### Example 1: Check README

```bash
#!/bin/bash
# Check if README exists and has content

if [[ ! -f README.md ]]; then
    echo "No README.md found"
    exit 2
fi

lines=$(wc -l < README.md)
if [[ $lines -lt 5 ]]; then
    echo "README too short: $lines lines"
    exit 2
fi

echo "README OK: $lines lines"
exit 0
```

**Result**: `exit_code=0, stdout="README OK: 42 lines"`

### Example 2: Validate Python Dependencies

```python
#!/python
import subprocess
import sys

try:
    deps = ['numpy', 'scipy', 'scikit-learn']
    for dep in deps:
        __import__(dep)
        print(f"✓ {dep}")
    exit(0)
except ImportError as e:
    print(f"✗ {e}")
    exit(2)
```

**Result**: `exit_code=2, stdout="✓ numpy\n✗ tensorflow (no module named 'tensorflow')"`

### Example 3: Parse Results from Output

```python
#!/python
import json
import re

try:
    with open('results.json') as f:
        data = json.load(f)
    
    accuracy = data.get('accuracy')
    if accuracy is None:
        print("No accuracy field found")
        exit(1)  # Undetermined
    
    print(f"Accuracy: {accuracy}")
    exit(0)
except Exception as e:
    print(f"Error: {e}")
    exit(2)
```

**Result**: `exit_code=0 or 1 or 2 depending on result`

---

## Summary

| Aspect | Details |
|--------|---------|
| **Simplicity** | Just text scripts with shebang, no complex plugin system |
| **User Control** | Users upload scripts, specify when they run (after clone/install/code) |
| **Execution** | Agent executes in container, sends results back via events |
| **Results** | Three exit codes (0/1/2), stdout/stderr captured, displayed live |
| **Storage** | Results stored in database for later inspection |
| **Real-time** | Users see output in live event feed as scripts execute |
| **Flexibility** | Any interpreter (bash, python, node, ruby, perl, etc.) |
| **Isolation** | Scripts are independent, don't interfere with each other |

This is much simpler than a full plugin system, gives users full power, and integrates cleanly with the existing agent/event architecture.
