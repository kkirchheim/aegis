# Storage Limit Configuration Implementation

## Overview
Added storage limit configuration to execution containers in the paper-reproducibility project. Users can now specify temporary storage limits (1-100 GB) for agent containers when analyzing papers.

## Changes Made

### 1. Config Panel (templates/index.html)
**Location:** Analysis Configuration section

**Change:**
```html
<!-- Storage Limit -->
<div>
    <label class="label">
        <span class="label-text">Storage Limit (GB)</span>
    </label>
    <input type="number" id="storageLimit" class="input input-bordered w-full" value="10" min="1" max="100" step="1" />
</div>
```

**Details:**
- Input field for storage limit (1-100 GB range)
- Default value: 10 GB
- Placed in "Analysis Configuration" section alongside other resource limits
- Integrated into the existing grid layout

### 2. JavaScript Handler (static/app.js)
**Location:** `handleAnalyzeClick()` function

**Change:**
```javascript
formData.append("storage_limit", document.getElementById("storageLimit").value);
```

**Details:**
- Captures storage_limit from HTML form input on submission
- Includes in POST /upload payload as part of form data
- Submitted alongside other configuration parameters (cpu_limit, memory_limit, etc.)

### 3. Backend API (app.py)
**Location:** `/upload` endpoint

**Change:**
```python
config = {
    "container": request.form.get("container", "python"),
    "model": request.form.get("model", "haiku"),
    "cpu_limit": int(request.form.get("cpu_limit", 4)),
    "memory_limit": int(request.form.get("memory_limit", 2048)),
    "runtime_limit": int(request.form.get("runtime_limit", 30)),
    "max_iterations": int(request.form.get("max_iterations", 3)),
    "storage_limit": int(request.form.get("storage_limit", 10))
}
```

**Details:**
- Extracts storage_limit from form request
- Validates as integer
- Default: 10 GB
- Passed to `analyze_paper_background()` function in config dict
- Config dict passed from `/upload` to `analyze_paper_background(job_id, str(pdf_path), config)`

### 4. Container Spawning (app.py - spawn_agent_container)
**Location:** `spawn_agent_container(job_id, repo_url, config=None)` function

**Changes:**

#### A. Function Signature
```python
def spawn_agent_container(job_id, repo_url, config=None):
    """
    Spawn Docker container to run agent on repository.
    
    Args:
        job_id: Unique job identifier
        repo_url: Repository URL to analyze
        config: Optional configuration dict with limits:
            - storage_limit: Storage limit in GB (1-100, default 10)
            - memory_limit: Memory in MB
            - cpu_limit: CPU cores
    """
    # Use defaults if config not provided
    if config is None:
        config = {
            "storage_limit": 10,
            "memory_limit": 2048,
            "cpu_limit": 2
        }
```

#### B. Storage Limit Validation
```python
# Validate and extract storage limit
storage_limit = config.get("storage_limit", 10)
try:
    storage_limit = int(storage_limit)
    if storage_limit < 1 or storage_limit > 100:
        app.logger.warning(f"[{job_id}] Storage limit {storage_limit}GB out of range (1-100), using default 10GB")
        storage_limit = 10
except (ValueError, TypeError):
    app.logger.warning(f"[{job_id}] Invalid storage limit value, using default 10GB")
    storage_limit = 10

storage_limit_str = f"{storage_limit}g"
```

**Validation:**
- Range check: 1-100 GB
- Type validation: Convert to int
- Fallback: Default to 10 GB on any error
- Logged warning for out-of-range values

#### C. Docker Container Configuration
```python
container = docker_client.containers.run(
    "paper-reproducibility-agent:latest",
    detach=True,
    name=container_name,
    environment={
        "REPO_URL": repo_url,
        "JOB_ID": job_id,
        "BACKEND_URL": backend_url,
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "STORAGE_LIMIT": storage_limit_str
    },
    mem_limit="2g",
    memswap_limit="2g",
    nano_cpus=int(2 * 1e9),
    tmpfs={"/tmp": f"size={storage_limit_str}"},  # NEW: Limit /tmp storage
    network="workspace_traefik",
    remove=False,
    stdout=True,
    stderr=True
)
```

**Docker Changes:**
- Added `tmpfs={"/tmp": f"size={storage_limit_str}"}` to limit /tmp temporary storage
- Added `STORAGE_LIMIT` environment variable for agent to read (if needed)
- Logging shows "Storage Limit: {storage_limit}GB" during container startup

#### D. Config Passing
```python
# In analyze_paper_background, when spawning agents:
spawn_agent_container(job_id, repo_url, config)
```

### 5. Logging
**Location:** Container startup logs

**Output:**
```
[job_id] Starting container with:
[job_id]   Memory: 2GB
[job_id]   CPU: 2 cores (nano_cpus=2000000000)
[job_id]   Storage Limit: 10GB
[job_id]   Network: workspace_traefik (shared with Flask app)
```

## How It Works

### User Flow
1. User opens analysis page
2. Configures analysis parameters including "Storage Limit (GB)"
3. Uploads PDF and clicks "Analyze Paper"
4. Frontend captures storage_limit value (1-100 GB)
5. Sends to `/upload` endpoint via form data

### Backend Flow
1. `/upload` endpoint receives storage_limit in request.form
2. Validates as integer in range 1-100 (default 10)
3. Includes in config dict passed to `analyze_paper_background()`
4. `analyze_paper_background()` passes config to `spawn_agent_container()`
5. `spawn_agent_container()` validates storage_limit again
6. Creates Docker container with `--tmpfs /tmp:size={limit}g`
7. Logs the storage limit during startup

### Docker Container Effect
- The `--tmpfs /tmp:size={limit}g` flag limits temporary filesystem usage
- When container attempts to write more than {limit} to /tmp, disk is full
- Agent code will fail with disk space errors if exceeding limit
- Container can still access rest of filesystem normally
- Multiple agents can run simultaneously with different storage limits

## Testing Checklist

- [x] HTML input field added to config section
- [x] Input field has correct attributes (min=1, max=100, default=10)
- [x] JavaScript captures and sends storage_limit
- [x] app.py accepts storage_limit parameter
- [x] Storage_limit validated (1-100 GB range)
- [x] Default fallback (10 GB) works
- [x] Config passed through analyze_paper_background
- [x] Config passed to spawn_agent_container
- [x] Docker tmpfs flag applied
- [x] Storage_limit logged during container startup
- [x] Environment variable set for agent

## Future Enhancements

- Add validation in frontend for min/max values
- Add tooltip explaining storage limit purpose
- Store user's preferred storage limit in database
- Monitor actual /tmp usage and warn if approaching limit
- Add option to increase limit for large code repositories

## Notes

- Default is 10 GB (reasonable for most analyses)
- Validation ensures range 1-100 GB
- If storage_limit not provided, defaults to 10 GB
- Storage limit applies only to /tmp, not entire filesystem
- Docker will enforce the limit via tmpfs mount
- Agent can read STORAGE_LIMIT env var if custom handling needed
