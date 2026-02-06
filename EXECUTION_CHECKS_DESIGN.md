# Execution Checks (Plugins) - Design & Implementation Plan

## Problem Statement

Currently, reproducibility evaluation happens entirely in **Stage 3** after the container is destroyed. This has two issues:

1. **Lost Opportunity**: The container (with filesystem, environment, running processes) exists during Stage 2 but isn't inspected until it's gone
2. **Non-Determinism**: LLM-based evaluation can be affected by prompt changes (e.g., adding a new aspect plugin can subtly change all results)
3. **Missed Checks**: Some checks are better as deterministic code (faster, more reliable, always the same)

**Solution**: Add **Execution Checks** (plugins) that run **during Stage 2**, inside the container, while it exists.

---

## Architecture Overview

### Components

```
                       STAGE 2 (EXECUTION)
                   ─────────────────────────────

1. Clone Repo    →  2. Run Checks  →  3. Install Deps  →  4. Run Code  →  5. Collect Results
                        (Phase 1)                              (Phase 3)
                    
   ┌─────────────────────────────┐
   │  Execution Checks (Plugins) │
   ├─────────────────────────────┤
   │ - README.md exists?         │
   │ - requirements.txt valid?   │
   │ - Main script exists?       │
   │ - (custom user checks)      │
   └─────────────────────────────┘
            ↓
      Check Results ──→ Stored in database
            ↓
      Available to Stage 3 for evaluation
```

### Timing

```
Stage 2 Timeline:
─────────────────────────────────────────────────────────────────
[Clone]  →  [CHECKS Phase 1]  →  [Install]  →  [Run Code]  →  [CHECKS Phase 2]  →  [Cleanup]
                (repo exists)                  (deps installed)   (after execution)
```

---

## Data Model

### 1. ExecutionCheck Model
Defines a single check (like "README exists").

```python
class ExecutionCheck(BaseModel):
    """Execution check definition."""
    id = UUIDField(primary_key=True)
    name = CharField()                    # "README Exists"
    description = TextField()             # "Verify README.md exists and is not empty"
    
    # When to run this check
    phase = CharField()                   # 'after_clone', 'after_install', 'after_execution'
    
    # What type of check
    check_type = CharField()              # 'script', 'metadata', 'output_pattern'
    
    # Check definition
    script = TextField(null=True)         # Bash/Python script to run
    metadata_path = CharField(null=True)  # File/dir to check existence
    output_pattern = CharField(null=True) # Regex pattern to match in stdout
    timeout_seconds = IntegerField()      # Max runtime for this check (default 30)
    
    # Metadata
    is_default = BooleanField()           # System-provided or custom?
    created_at = DateTimeField()
    created_by = ForeignKeyField(User)
```

### 2. UserExecutionCheck Model
Per-user configuration of checks.

```python
class UserExecutionCheck(BaseModel):
    """User's settings for execution checks."""
    id = UUIDField(primary_key=True)
    user = ForeignKeyField(User)
    check = ForeignKeyField(ExecutionCheck)
    
    is_active = BooleanField()            # Is this check enabled?
    custom_script = TextField(null=True)  # User override of script
    severity = CharField()                # 'warn' (non-blocking) or 'fail' (stop job)
    
    deleted_at = DateTimeField(null=True) # Soft delete
    created_at = DateTimeField()
```

### 3. ExecutionCheckResult Model
Results of running a check.

```python
class ExecutionCheckResult(BaseModel):
    """Result of a single check execution."""
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job)
    check = ForeignKeyField(ExecutionCheck)
    
    status = CharField()                  # 'PASS', 'FAIL', 'ERROR', 'SKIPPED'
    output = TextField(null=True)         # stdout/stderr from check
    error_message = TextField(null=True)  # If status='ERROR'
    
    # For debugging
    runtime_ms = IntegerField()           # How long check took
    phase = CharField()                   # When it ran
    
    created_at = DateTimeField()
```

---

## Check Types

### 1. Script-Based Checks
Run arbitrary bash/python code **inside the container**.

```python
# Example: Check if README exists and is not empty
{
    "type": "script",
    "phase": "after_clone",
    "script": """
        #!/bin/bash
        
        # Look for readme file (case-insensitive)
        readme=$(find . -maxdepth 1 -iname 'readme*' -type f 2>/dev/null | head -1)
        
        if [ -z "$readme" ]; then
            echo "README file not found"
            exit 1
        fi
        
        # Check if file is not empty
        if [ ! -s "$readme" ]; then
            echo "README file is empty"
            exit 1
        fi
        
        echo "README found: $readme"
        echo "Size: $(wc -c < "$readme") bytes"
        exit 0
    """,
    "timeout_seconds": 10,
    "severity": "warn"  # Don't fail job if check fails
}
```

### 2. Metadata Checks
Check for file/directory existence without running code.

```python
# Example: requirements.txt exists
{
    "type": "metadata",
    "phase": "after_clone",
    "metadata_path": "requirements.txt",  # Check exact path
    "severity": "warn"
}

# Can also use patterns:
{
    "type": "metadata",
    "phase": "after_clone",
    "metadata_path": "*.txt|requirements*",  # Glob or regex
    "severity": "fail"  # Fail job if not found
}
```

### 3. Output Pattern Checks
Search for patterns in command output.

```python
# Example: Check that stderr contains no "fatal" errors
{
    "type": "output_pattern",
    "phase": "after_execution",
    "output_pattern": "fatal.*error",  # Regex pattern
    "invert": True,  # PASS if pattern NOT found
    "severity": "warn"
}
```

---

## Execution Flow

### During Stage 2

```python
def _run_stage_2(job_id, config):
    """Stage 2: Execute code from artifacts."""
    
    # Initialize container
    container = spawn_docker_container(job_id)
    
    try:
        # Step 1: Clone repository
        container.run("git clone ...")
        
        # PHASE 1: After clone checks
        execute_checks(job_id, container, phase="after_clone")
        
        # Step 2: Install dependencies
        container.run("pip install -r requirements.txt")
        
        # PHASE 2: After install checks
        execute_checks(job_id, container, phase="after_install")
        
        # Step 3: Run code
        container.run("python main.py")
        
        # PHASE 3: After execution checks
        execute_checks(job_id, container, phase="after_execution")
        
    finally:
        # Container destroyed here (checks are done!)
        container.stop()
```

### Check Execution Function

```python
def execute_checks(job_id, container, phase):
    """Run all active checks for this phase."""
    
    from models.database import UserExecutionCheck, ExecutionCheckResult
    from services.job_service import get_job
    
    job = get_job(job_id)
    user_id = job.user_id
    
    # Get all active checks for this phase
    active_checks = (
        UserExecutionCheck
        .select()
        .join(ExecutionCheck)
        .where(
            (UserExecutionCheck.user_id == user_id) &
            (UserExecutionCheck.is_active == True) &
            (UserExecutionCheck.deleted_at.is_null()) &
            (ExecutionCheck.phase == phase)
        )
    )
    
    for user_check in active_checks:
        check = user_check.check
        
        try:
            result = run_single_check(
                job_id=job_id,
                container=container,
                check=check,
                user_override_script=user_check.custom_script
            )
            
            # Store result
            ExecutionCheckResult.create(
                job_id=job_id,
                check_id=check.id,
                status=result['status'],
                output=result['output'],
                error_message=result['error'],
                runtime_ms=result['runtime_ms'],
                phase=phase
            )
            
            # If severity='fail' and check failed, stop execution
            if user_check.severity == 'fail' and result['status'] in ['FAIL', 'ERROR']:
                raise ExecutionCheckFailed(f"Check failed: {check.name}")
        
        except Exception as e:
            logger.error(f"Check {check.name} failed: {e}")
            # Store error result
            ExecutionCheckResult.create(
                job_id=job_id,
                check_id=check.id,
                status='ERROR',
                error_message=str(e),
                phase=phase
            )


def run_single_check(job_id, container, check, user_override_script):
    """Execute a single check inside the container."""
    
    start = time.time()
    
    try:
        if check.check_type == 'script':
            # Run custom script
            script = user_override_script or check.script
            result = container.exec_run(
                cmd=['bash', '-c', script],
                timeout=check.timeout_seconds
            )
            status = 'PASS' if result.exit_code == 0 else 'FAIL'
            output = result.output.decode('utf-8', errors='replace')
        
        elif check.check_type == 'metadata':
            # Check file/directory existence
            result = container.exec_run(['test', '-e', check.metadata_path])
            status = 'PASS' if result.exit_code == 0 else 'FAIL'
            output = f"Path exists: {check.metadata_path}" if status == 'PASS' else f"Path missing: {check.metadata_path}"
        
        elif check.check_type == 'output_pattern':
            # Search for pattern in execution stdout
            pattern = check.output_pattern
            invert = check.invert
            # Get stdout from container logs
            stdout = container.logs()
            found = bool(re.search(pattern, stdout))
            if invert:
                found = not found
            status = 'PASS' if found else 'FAIL'
            output = f"Pattern {'found' if found else 'not found'}: {pattern}"
    
    except Exception as e:
        status = 'ERROR'
        output = None
        error_message = str(e)
    
    runtime_ms = int((time.time() - start) * 1000)
    
    return {
        'status': status,
        'output': output,
        'error': error_message if status == 'ERROR' else None,
        'runtime_ms': runtime_ms
    }
```

---

## User Interface

### 1. Execution Checks Management Page
Similar to Aspects page, but for execution checks.

```
/execution-checks

[List of all execution checks]
├─ README Documentation Check (PASS rate: 92%)
│  └ [Edit] [Activate/Deactivate] [Override Script]
├─ Requirements.txt Validation (PASS rate: 88%)
│  └ [Edit] [Activate/Deactivate] [Override Script]
└─ Custom Python Validation (User-created)
   └ [Edit] [Delete] [Activate/Deactivate]

[+ Add Custom Check]
```

### 2. Check Details Modal
```
Check: README Documentation

Description: Verify README.md exists and is not empty

Type: Script
Phase: after_clone
Severity: warn (non-blocking)
Timeout: 10 seconds

Script (editable):
┌─────────────────────────────────────┐
│ #!/bin/bash                         │
│ readme=$(find . -maxdepth 1 ...)    │
│ ...                                 │
└─────────────────────────────────────┘

[Save] [Reset to Default] [Test on Past Jobs]
```

### 3. Check Results in Job Detail Page
```
Execution Checks Results (Phase: after_clone)
├─ ✓ README Documentation (8ms)
│  └ "README found: README.md, Size: 1245 bytes"
├─ ✓ Requirements.txt Exists (5ms)
│  └ "Path exists: requirements.txt"
└─ ✗ Main Script Found (3ms)
   └ "Path missing: main.py" (Warning - non-blocking)

Execution Checks Results (Phase: after_execution)
├─ ✓ No Fatal Errors (2ms)
│  └ "Pattern not found in output (as expected)"
└─ ⚠ Results Match Paper (45ms)
   └ ERROR: "Pattern 'accuracy.*0\\.93' not found"
```

---

## Database Schema Changes

```sql
-- New tables
CREATE TABLE execution_check (
    id UUID PRIMARY KEY,
    name VARCHAR,
    description TEXT,
    phase VARCHAR CHECK (phase IN ('after_clone', 'after_install', 'after_execution')),
    check_type VARCHAR CHECK (check_type IN ('script', 'metadata', 'output_pattern')),
    script TEXT,
    metadata_path VARCHAR,
    output_pattern VARCHAR,
    timeout_seconds INT DEFAULT 30,
    is_default BOOLEAN,
    created_at TIMESTAMP,
    created_by INT REFERENCES user(id)
);

CREATE TABLE user_execution_check (
    id UUID PRIMARY KEY,
    user_id INT REFERENCES user(id),
    check_id UUID REFERENCES execution_check(id),
    is_active BOOLEAN DEFAULT TRUE,
    custom_script TEXT,
    severity VARCHAR CHECK (severity IN ('warn', 'fail')) DEFAULT 'warn',
    deleted_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE execution_check_result (
    id UUID PRIMARY KEY,
    job_id VARCHAR REFERENCES job(id),
    check_id UUID REFERENCES execution_check(id),
    status VARCHAR CHECK (status IN ('PASS', 'FAIL', 'ERROR', 'SKIPPED')),
    output TEXT,
    error_message TEXT,
    runtime_ms INT,
    phase VARCHAR,
    created_at TIMESTAMP
);

-- Link execution details to check results
ALTER TABLE execution_details 
ADD COLUMN check_results JSON;  -- Summary of all check results
```

---

## Default Execution Checks

System provides pre-built checks for common scenarios:

```
1. README Documentation
   Type: script, Phase: after_clone
   Checks: README exists and is not empty
   Severity: warn

2. Requirements.txt Present
   Type: metadata, Phase: after_clone
   Checks: requirements.txt exists
   Severity: warn

3. Main Script Exists
   Type: metadata, Phase: after_clone
   Checks: main.py or setup.py exists
   Severity: warn

4. Dependencies Installed
   Type: script, Phase: after_install
   Checks: pip list output contains expected packages
   Severity: warn

5. No Fatal Errors
   Type: output_pattern, Phase: after_execution
   Checks: stderr does NOT contain "fatal"
   Severity: warn

6. Code Produced Output
   Type: script, Phase: after_execution
   Checks: stdout is not empty
   Severity: warn
```

---

## Determinism Guarantees

### Problem: New Check Affects Others

If I add a new aspect plugin, the LLM prompt changes, which can affect ALL evaluation results (non-deterministic).

### Solution: Execution Checks Don't Affect Each Other

1. **Isolation**: Each check stores its own result independently
2. **No Interference**: One check's failure doesn't affect others (unless severity='fail')
3. **Stable Results**: If you run the same checks twice, you get the same results
4. **Stage 3 Aggregation**: LLM evaluation uses check results as additional context, but doesn't change if checks are added

```
Before: LLM sees only container output (non-deterministic if prompt changes)
After:  LLM sees container output + deterministic check results (more robust)
```

---

## Integration with Aspect Evaluation (Stage 3)

Execution checks provide **input** to aspect evaluation, not replacement:

```
Stage 3 Evaluation (LLM-based):

Input:
├─ Paper text (from Stage 1)
├─ Container stdout (from Stage 2)
├─ Execution check results (NEW!) ✓
│  ├─ README Documentation: PASS
│  ├─ Requirements.txt: PASS
│  └─ Code Produced Output: FAIL
├─ Aspect plugins (prompts)
└─ Active aspects for this user

LLM combines all inputs to evaluate:
- Code Availability: (uses check results + paper analysis)
- Reproducibility: (uses check results + stdout + paper claims)
- etc.
```

**Benefits**:
- LLM has deterministic facts to work with
- Can reason about hard failures (check said "FAIL") vs. soft issues
- Results are reproducible and auditable
- Code-based checks don't interfere with each other

---

## Implementation Phases

### Phase 1: Infrastructure (Week 1)
- [ ] Create models: ExecutionCheck, UserExecutionCheck, ExecutionCheckResult
- [ ] Create migrations
- [ ] Implement check execution engine (run_single_check)
- [ ] Integrate into Stage 2 pipeline (add execute_checks calls)

### Phase 2: Built-in Checks (Week 1-2)
- [ ] Create 6 default checks
- [ ] Seed checks on first user login
- [ ] Store results in database

### Phase 3: User Interface (Week 2)
- [ ] Execution checks management page (/execution-checks)
- [ ] Check details modal with script editor
- [ ] Check results display in job detail page
- [ ] Create/edit/delete custom checks

### Phase 4: Testing & Hardening (Week 2-3)
- [ ] Test check execution in container
- [ ] Test error handling (timeout, crash, etc.)
- [ ] Test determinism (same results on replay)
- [ ] Performance testing (overhead of checks)

### Phase 5: Documentation (Week 3)
- [ ] User guide for writing custom checks
- [ ] API documentation
- [ ] Examples of useful checks

---

## Example Use Cases

### Use Case 1: Dataset Paper
**Problem**: Different repos have different standards (code papers vs. dataset papers)

**Solution**: Curator creates custom check:
```bash
# DatasetDownloadCheck
#!/bin/bash
# Verify dataset can be downloaded and extracted

cd data/ || exit 1
ls -la | head -20
# Check that at least one data file exists
find . -type f -size +0 | head -1
```

### Use Case 2: Accuracy Matching
**Problem**: README says "accuracy: 0.92" but paper says "0.93"

**Solution**: Create check:
```bash
#!/bin/bash
# Check README matches paper results

grep -i "accuracy" README.md | grep -E "0\.93|93%"
```

### Use Case 3: Reproducibility Gate
**Problem**: Don't want to run LLM evaluation on repos that obviously fail

**Solution**: Add fail-severity check:
```python
# Severity: fail (blocks further execution if check fails)
# Phase: after_execution
# Type: script

#!/bin/bash
# Check that code executed without fatal errors
! grep -i "traceback\|fatal\|segmentation" output.log
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **What** | Deterministic checks run inside container during Stage 2 |
| **When** | After clone, after install, after execution |
| **Types** | Script-based, metadata-based, pattern-based |
| **User Control** | Create custom checks, override defaults, activate/deactivate |
| **Results** | Stored in database, used by Stage 3 evaluation |
| **Determinism** | Isolated, non-interfering with each other |
| **Flexibility** | Still use LLM for final evaluation, but with hard facts |
| **Fallback** | If check fails, LLM evaluation still runs (unless severity=fail) |

This design gives you:
- ✅ Deterministic code checks
- ✅ Real-time evaluation (while container exists)
- ✅ User customization (plugins)
- ✅ Hybrid approach (code + LLM)
- ✅ Auditability (all results stored)
- ✅ Performance (code is faster than LLM)
