# Execution Scripts - Implementation Plan (V2 - Based on Actual Architecture)

## Current Architecture

The system uses a **Claude agent running inside the container** that makes decisions about what to do:

```
┌─────────────────────────────────────────┐
│ Docker Container (Agent Sandbox)        │
├─────────────────────────────────────────┤
│                                         │
│  Loop:                                  │
│  1. Call /agent/think                   │
│  2. Get action from Claude              │
│  3. Execute action locally (read/run)   │
│  4. Go back to step 1                   │
│                                         │
│  Repo is cloned ONCE at start           │
│  Persists across iterations             │
│                                         │
└─────────────────────────────────────────┘
         ↑                    ↓
    /agent/think        action: "read_file" | 
    /agent/log          action: "run_command" |
    /agent/execution    action: "check_success" |
    /agent/complete     action: "done"
         ↑                    ↓
┌─────────────────────────────────────────┐
│ Backend Controller                      │
├─────────────────────────────────────────┤
│ Calls Claude LLM                        │
│ Returns next action to agent            │
└─────────────────────────────────────────┘
```

## Problem with Current Design

The agent (Claude) decides all actions, including what scripts to run. This means:
- Scripts are handled by LLM → non-deterministic
- New scripts in prompt can affect other evaluations
- No guarantee script will run consistently

## Solution: Separate Script Execution Track

Scripts should run **outside the LLM decision loop**:

```
Docker Container Agent Loop:

Phase 1: Clone + Run User Scripts (after_clone)
  ├─ git clone repo
  └─ FOR EACH script:
  │   ├─ Parse shebang (#!bash, #!python)
  │   ├─ Execute (deterministic, no LLM involved)
  │   ├─ Capture exit code (0/1/2)
  │   ├─ Emit event: script_executed
  │   └─ Store result in memory
  │
  └─ Proceed to Phase 2

Phase 2: Claude Agent Loop (existing)
  ├─ Call /agent/think
  ├─ Get action from Claude
  ├─ Execute action (read/run/check_success/done)
  ├─ Call /agent/log or /agent/execution
  └─ Loop until done

Phase 3: After Code Execution
  └─ Run scripts again (after_code phase)
```

Key difference: **Scripts run directly, not through Claude**.

---

## Data Model

### ExecutionScript (New Table)

```python
class ExecutionScript(BaseModel):
    """User-provided script to run in container."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)  # Which job uses this script
    
    # Script definition
    script_text = TextField()           # Full script with shebang
    name = CharField()                  # User-friendly name
    description = TextField(null=True)  # What does it do
    
    # When to run
    run_after_clone = BooleanField()    # Run after git clone
    run_after_install = BooleanField()  # Run after pip install (before agent loop)
    run_after_code = BooleanField()     # Run after code execution (before /agent/complete)
    run_order = IntegerField()          # Order (1, 2, 3...)
    
    # Metadata
    created_at = DateTimeField()
    created_by = ForeignKeyField(User, null=True)
```

### ExecutionScriptResult (New Table)

```python
class ExecutionScriptResult(BaseModel):
    """Result of running a script."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)
    script = ForeignKeyField(ExecutionScript)
    
    # Result data
    exit_code = IntegerField()          # 0: success, 1: undetermined, 2: failure
    stdout = TextField(null=True)       # Output captured
    stderr = TextField(null=True)       # Errors captured
    
    # Timing
    started_at = DateTimeField()
    duration_ms = IntegerField()
    
    # Phase
    phase = CharField()                 # 'after_clone', 'after_install', 'after_code'
    
    created_at = DateTimeField()
```

---

## Agent-Side Execution (in Container)

The agent runs a simple Python script that doesn't call Claude for script execution:

```python
# pseudo-code for agent loop structure

class Agent:
    def __init__(self, job_id, repo_url, backend_url):
        self.job_id = job_id
        self.repo_url = repo_url
        self.backend_url = backend_url  # localhost or DOCKER_BACKEND_URL
        self.scripts = []  # Provided by backend
    
    async def run(self):
        # Phase 1: Clone repo
        self.clone_repo()
        
        # Phase 1: Run user scripts (deterministic, no LLM)
        await self.run_scripts_phase('after_clone')
        
        # Phase 2: Agent loop (existing Claude loop)
        # This is the existing /agent/think loop
        await self.agent_loop_phase()
        
        # Phase 3: Run scripts after code execution
        await self.run_scripts_phase('after_code')
        
        # Mark complete
        await self.call_backend('/agent/complete')
    
    async def run_scripts_phase(self, phase):
        """Run all scripts for a phase."""
        scripts_for_phase = [
            s for s in self.scripts
            if phase == 'after_clone' and s['run_after_clone']
            or phase == 'after_install' and s['run_after_install']
            or phase == 'after_code' and s['run_after_code']
        ]
        
        # Sort by run_order
        scripts_for_phase.sort(key=lambda s: s.get('run_order', 0))
        
        for script in scripts_for_phase:
            result = self.execute_script(script)
            
            # Emit event (streamed to user)
            await self.emit_event({
                'event': 'script_executed',
                'script_id': script['id'],
                'script_name': script['name'],
                'phase': phase,
                'exit_code': result['exit_code'],
                'stdout': result['stdout'],
                'stderr': result['stderr'],
                'duration_ms': result['duration_ms']
            })
            
            # Store result on backend
            await self.call_backend(
                '/script/result',
                method='POST',
                json={
                    'script_id': script['id'],
                    'exit_code': result['exit_code'],
                    'stdout': result['stdout'],
                    'stderr': result['stderr'],
                    'duration_ms': result['duration_ms'],
                    'phase': phase
                }
            )
    
    def execute_script(self, script_def):
        """Execute a single script in container."""
        import subprocess
        import tempfile
        import time
        
        script_text = script_def['script_text']
        
        try:
            # Parse shebang
            interpreter, script_body = self.parse_shebang(script_text)
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix=self.get_file_extension(interpreter)
            ) as f:
                f.write(script_body)
                temp_script = f.name
            
            # Make executable
            import os
            os.chmod(temp_script, 0o755)
            
            # Execute
            start_time = time.time()
            
            result = subprocess.run(
                [interpreter, temp_script],
                capture_output=True,
                timeout=300,  # 5 minute max
                text=True,
                cwd=self.repo_path  # Run in cloned repo directory
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Validate exit code
            exit_code = result.returncode
            if exit_code not in [0, 1, 2]:
                exit_code = 2  # Treat unexpected codes as failure
            
            return {
                'exit_code': exit_code,
                'stdout': result.stdout[:10000],  # Limit output size
                'stderr': result.stderr[:10000],
                'duration_ms': duration_ms
            }
        
        except subprocess.TimeoutExpired:
            return {
                'exit_code': 2,
                'stdout': '',
                'stderr': 'Script timeout after 5 minutes',
                'duration_ms': 5 * 60 * 1000
            }
        except Exception as e:
            return {
                'exit_code': 2,
                'stdout': '',
                'stderr': str(e),
                'duration_ms': 0
            }
    
    @staticmethod
    def parse_shebang(script_text):
        """Extract interpreter from shebang."""
        lines = script_text.split('\n')
        if not lines or not lines[0].startswith('#!'):
            raise ValueError("Script must start with shebang (e.g., #!bash, #!python)")
        
        interpreter = lines[0][2:].strip()
        
        # Map common shebang names to actual executables
        mapping = {
            'bash': '/bin/bash',
            'sh': '/bin/sh',
            'python': 'python3',
            'python3': 'python3',
            'node': 'node',
            'ruby': 'ruby',
        }
        
        cmd = mapping.get(interpreter, interpreter)
        script_body = '\n'.join(lines[1:])
        
        return cmd, script_body
    
    @staticmethod
    def get_file_extension(interpreter):
        """Get temp file extension based on interpreter."""
        return {
            'bash': '.sh',
            'sh': '.sh',
            'python3': '.py',
            'python': '.py',
            'node': '.js',
            'ruby': '.rb',
        }.get(interpreter, '.txt')
```

---

## Backend Changes

### 1. Pass Scripts to Agent

When spawning container, pass scripts via job config:

```python
# In docker_service.py spawn_agent_container()

scripts = ExecutionScript.select().where(ExecutionScript.job == job_id)

container_kwargs["environment"]["JOB_CONFIG"] = json.dumps({
    "job_id": job_id,
    "repo_url": repo_url,
    "scripts": [
        {
            "id": str(s.id),
            "name": s.name,
            "script_text": s.script_text,
            "run_after_clone": s.run_after_clone,
            "run_after_install": s.run_after_install,
            "run_after_code": s.run_after_code,
            "run_order": s.run_order,
        }
        for s in scripts
    ]
})
```

### 2. New Backend Endpoint: Script Results

```python
# In blueprints/api.py

@api_bp.route("/script/result", methods=["POST"])
@use_kwargs(ScriptResultSchema, location="json")
def script_result(job_id, script_id, exit_code, stdout, stderr, duration_ms, phase):
    """Agent reports script execution result."""
    
    # Validate job
    job = Job.get_by_id(job_id)
    if not job:
        return {"error": "Invalid job_id"}, 404
    
    # Store result
    ExecutionScriptResult.create(
        job=job,
        script_id=script_id,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        phase=phase,
        started_at=datetime.now()
    )
    
    # Emit event to user
    emit_event(job_id, {
        'event': 'script_executed',
        'script_id': script_id,
        'exit_code': exit_code,
        'stdout': stdout,
        'phase': phase
    })
    
    return {"ok": True}
```

### 3. API Endpoints for Script Management

```python
@api_bp.route("/job/<job_id>/scripts", methods=["POST"])
def add_script(job_id):
    """User adds script to job."""
    data = request.json
    
    script = ExecutionScript.create(
        job_id=job_id,
        name=data['name'],
        script_text=data['script_text'],
        run_after_clone=data.get('run_after_clone', False),
        run_after_install=data.get('run_after_install', False),
        run_after_code=data.get('run_after_code', False),
        run_order=data.get('run_order', 0)
    )
    
    return {"id": str(script.id), "created_at": script.created_at}, 201

@api_bp.route("/job/<job_id>/scripts", methods=["GET"])
def list_scripts(job_id):
    """Get scripts for a job."""
    scripts = ExecutionScript.select().where(ExecutionScript.job == job_id)
    return {
        "scripts": [
            {
                "id": str(s.id),
                "name": s.name,
                "script_text": s.script_text,
                "run_after_clone": s.run_after_clone
            }
            for s in scripts
        ]
    }

@api_bp.route("/job/<job_id>/scripts/<script_id>/results", methods=["GET"])
def script_results(job_id, script_id):
    """Get execution results for a script."""
    results = ExecutionScriptResult.select().where(
        (ExecutionScriptResult.job == job_id) &
        (ExecutionScriptResult.script == script_id)
    ).order_by(ExecutionScriptResult.created_at.desc())
    
    return {
        "results": [
            {
                "exit_code": r.exit_code,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "duration_ms": r.duration_ms,
                "phase": r.phase,
                "created_at": r.created_at
            }
            for r in results
        ]
    }
```

---

## Integration with Pipeline Orchestrator

No changes needed. Scripts are passed to agent via environment, agent handles them.

```python
def _run_stage_2(self, job_id: str, config) -> bool:
    """Stage 2: Execute code from artifacts."""
    
    try:
        # Get scripts for this job
        scripts = ExecutionScript.select().where(ExecutionScript.job == job_id)
        
        # Pass scripts to agent via environment
        spawn_agent_container(
            job_id=job_id,
            repo_url=artifact_url,
            config=config,
            scripts=scripts,  # ← Agent will execute these
            emit_event=self.emit_event
        )
        
        return True
    except Exception as e:
        return False
```

---

## Frontend

### Upload Script Form

```html
<section class="card">
  <h2>Execution Scripts</h2>
  
  <textarea id="scriptContent" 
            placeholder="#!bash&#10;test -f README.md && exit 0 || exit 1"
            class="textarea textarea-bordered font-mono"></textarea>
  
  <div class="form-control">
    <label class="label">
      <input type="checkbox" id="runAfterClone" checked />
      <span>Run after clone</span>
    </label>
    <label class="label">
      <input type="checkbox" id="runAfterInstall" />
      <span>Run after install</span>
    </label>
    <label class="label">
      <input type="checkbox" id="runAfterCode" />
      <span>Run after code execution</span>
    </label>
  </div>
  
  <button onclick="addScript()">Add Script</button>
</section>
```

### Live Event Display

```
[14:31:20] ─────────────────────────────────────
[14:31:20] Script: "Check README"
[14:31:20] Status: ✓ SUCCESS (exit code 0)
[14:31:20] Phase: after_clone
[14:31:20] Output: "README found, 1245 bytes"
[14:31:20] Duration: 45ms
[14:31:20] ─────────────────────────────────────
```

---

## Implementation Steps

### Step 1: Database (30 min)
- [ ] Create ExecutionScript model
- [ ] Create ExecutionScriptResult model
- [ ] Create migration

### Step 2: Agent (1-2 hours)
- [ ] Implement parse_shebang()
- [ ] Implement execute_script()
- [ ] Implement run_scripts_phase()
- [ ] Call backend `/script/result` endpoint
- [ ] Integrate into agent loop (before & after)

### Step 3: Backend API (1 hour)
- [ ] `/script/result` endpoint (agent reports)
- [ ] `/job/<id>/scripts` POST/GET (manage scripts)
- [ ] `/job/<id>/scripts/<sid>/results` GET (view results)
- [ ] Pass scripts to agent via environment

### Step 4: Frontend (1-2 hours)
- [ ] Script upload form
- [ ] Live event display
- [ ] Results view

### Step 5: Testing (1-2 hours)
- [ ] Unit tests: parse_shebang
- [ ] Integration tests: agent executes scripts
- [ ] E2E tests: script → result → UI

---

## Key Differences from Original Design

| Aspect | Original Design | This Design |
|--------|-----------------|-------------|
| **Where scripts run** | Both agent & orchestrator | Agent only |
| **LLM involvement** | Scripts go through LLM | Scripts NOT through LLM |
| **Determinism** | Affects other evaluations | Isolated, independent |
| **Timing** | Stage 2 checks | Before, during, after agent loop |
| **Complexity** | Plugin system | Simple script execution |
| **Control Flow** | Orchestrator decides when | Agent decides (phases) |

---

## Example Scripts

### Check README

```bash
#!/bin/bash
readme=$(find . -maxdepth 1 -iname 'readme*' | head -1)
[[ -z "$readme" ]] && exit 2
[[ $(wc -l < "$readme") -lt 3 ]] && exit 2
echo "README OK: $(wc -l < "$readme") lines"
exit 0
```

### Validate Python

```python
#!/python
import subprocess
deps = ['numpy', 'scipy']
for dep in deps:
    try:
        __import__(dep)
        print(f"✓ {dep}")
    except ImportError:
        print(f"✗ {dep}")
        exit(2)
exit(0)
```

### Parse Results

```python
#!/python
import json
with open('results.json') as f:
    data = json.load(f)
accuracy = data.get('accuracy')
print(f"Accuracy: {accuracy}")
exit(0 if accuracy else 1)
```

---

## Summary

- **Repo cloned once** ✓ (by agent at start)
- **Scripts run separately** ✓ (not through LLM)
- **Deterministic** ✓ (no prompt interference)
- **Real-time feedback** ✓ (events streamed to user)
- **Simple** ✓ (minimal code, uses existing infrastructure)
- **Flexible** ✓ (any interpreter, any logic)
