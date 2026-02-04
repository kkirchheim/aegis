# Storage Limit Configuration - Changes Summary

## Modified Files

### 1. templates/index.html
**Type:** UI Enhancement
**Changes:**
- Added storage limit input field to "Analysis Configuration" section
- Field specs: `<input type="number" id="storageLimit" value="10" min="1" max="100" step="1">`
- Located after "Max Iterations" field
- Label: "Storage Limit (GB)"

**Lines Modified:** Added storage limit div block within grid layout

### 2. static/app.js
**Type:** Frontend Logic
**Changes:**
- Added line to capture storage_limit from form input
- Appends to formData: `formData.append("storage_limit", document.getElementById("storageLimit").value);`
- Placed in `handleAnalyzeClick()` function alongside other config parameters

**Lines Modified:** 1 line added after max_iterations

### 3. app.py
**Type:** Backend API & Container Management
**Changes:**

#### A. /upload endpoint (line ~1290)
- Added storage_limit extraction to config dict
- `"storage_limit": int(request.form.get("storage_limit", 10))`
- Default: 10 GB

#### B. spawn_agent_container function signature (line 428)
- Changed from: `def spawn_agent_container(job_id, repo_url):`
- Changed to: `def spawn_agent_container(job_id, repo_url, config=None):`
- Added docstring documenting config parameter
- Added default config initialization

#### C. spawn_agent_container - validation logic (line ~475)
- Added validation for storage_limit (1-100 GB range)
- Handles ValueError/TypeError
- Logs warnings for out-of-range values
- Converts to string format: `storage_limit_str = f"{storage_limit}g"`

#### D. Docker container run call (line ~495)
- Added `tmpfs={"/tmp": f"size={storage_limit_str}"}` parameter
- Added `"STORAGE_LIMIT": storage_limit_str` to environment dict
- Updated logging to show: `f"[{job_id}]   Storage Limit: {storage_limit}GB"`

#### E. analyze_paper_background function (line ~2795)
- Updated call to spawn_agent_container to pass config
- Changed from: `spawn_agent_container(job_id, repo_url)`
- Changed to: `spawn_agent_container(job_id, repo_url, config)`

## New Files

### test_storage_limit.py
**Purpose:** Comprehensive test suite for storage limit implementation
**Tests:**
1. HTML input field presence and attributes
2. JavaScript capture and form submission
3. Backend parameter extraction and handling
4. Function signature updates
5. Validation logic (1-100 GB range)
6. Docker tmpfs configuration
7. Environment variable passing
8. Config parameter flow
9. Logging statements

**Status:** All 9 tests passing ✓

### STORAGE_LIMIT_IMPLEMENTATION.md
**Purpose:** Detailed implementation documentation
**Contents:**
- Overview and feature description
- Complete code changes for each component
- How the feature works (user flow, backend flow, Docker effect)
- Testing checklist
- Future enhancement suggestions

## Functional Requirements Met

✓ **Config Panel (index.html)**
- Added storage limit input field (1-100 GB, default 10GB)
- Input specs match requirement: `<input type="number" min="1" max="100" value="10">`
- Placed in "Analysis Configuration" section with other limits

✓ **JavaScript (app.js)**
- Captures storage_limit from form input on submission
- Includes in POST /upload payload as part of config object

✓ **Backend API (app.py)**
- Modified /upload endpoint to accept storage_limit parameter
- Validates range (1-100 GB) with sensible defaults
- Passes to analyze_paper_background() function

✓ **Agent Container Spawning (agent.py context)**
- spawn_agent_container accepts storage_limit parameter
- When creating Docker container, uses `--tmpfs /tmp:size={limit}g`
- Logs the storage limit being applied

✓ **Testing**
- Verify storage limit is passed through pipeline (✓ automated test)
- Verify Docker container respects limit (docker tmpfs flag applied)
- Test with different limit values (range 1-100 supported)

## Data Flow

```
User Form
    ↓
JavaScript captures storage_limit value
    ↓
POST to /upload with formData.storage_limit
    ↓
Flask extracts from request.form.get("storage_limit", 10)
    ↓
Stored in config dict: {"storage_limit": 10, ...}
    ↓
Passed to analyze_paper_background(job_id, pdf_path, config)
    ↓
Passed to spawn_agent_container(job_id, repo_url, config)
    ↓
Validated in spawn_agent_container (1-100 GB range)
    ↓
Applied to docker run command: --tmpfs /tmp:size=10g
    ↓
Agent container /tmp storage limited to specified GB
```

## Error Handling

- **Invalid value type:** Catches ValueError/TypeError, defaults to 10 GB
- **Out of range:** If < 1 or > 100, defaults to 10 GB with warning log
- **Missing parameter:** Defaults to 10 GB
- **Docker error:** If tmpfs fails, Docker will log error and container won't start

## Backward Compatibility

- storage_limit parameter is optional (default 10 GB)
- Existing code calling spawn_agent_container without config still works
- If config dict doesn't have storage_limit key, uses default 10 GB
- All changes are additive, no breaking changes

## Security Considerations

- Input validation: Range check ensures 1-100 GB
- Docker tmpfs: Inherently safe, limits only /tmp, not filesystem access
- No SQL injection risk: Integer parsing prevents injection
- No code execution risk: Storage limit is a filesystem constraint

## Performance Impact

- Minimal: Additional validation logic ~10 lines
- No I/O impact: tmpfs flag is standard Docker parameter
- No memory overhead: Validation is lightweight
- Logging: Debug-level info, minimal performance impact

## Rollback Plan

If needed to rollback:
1. Remove storage_limit input from index.html
2. Remove storage_limit from app.js formData
3. Remove "storage_limit" from config dict in app.py
4. Remove tmpfs parameter from docker run call
5. Remove STORAGE_LIMIT from environment variables
6. Remove validation logic
7. All changes are isolated and easily removable

## Deployment Notes

- No database schema changes required
- No environment variables required (STORAGE_LIMIT is internal)
- No Docker image rebuild required
- Frontend changes are automatic (served from templates/)
- Backend changes take effect after restart
- Can be deployed independently without other changes
