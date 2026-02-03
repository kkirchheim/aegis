# Stage 2 Quick Start Guide

## 30-Second Overview

Agent runs in Docker sandbox, clones repos, executes code, logs everything. Zero code runs on host.

```
Paper PDF → Claude finds repos → Agent per repo → Sandbox execution → Report
```

## Files Changed

**New Files:**
- `agent.py` - Agent script that runs in Docker
- `Dockerfile.agent` - Sandbox image
- `STAGE2_IMPLEMENTATION.md` - Full technical documentation
- `STAGE2_QUICKSTART.md` - This file

**Modified Files:**
- `app.py` - Added `/api/agent/think` + `/api/agent/log` + Docker spawning
- (No other files changed)

## Local Testing

### Option 1: Full End-to-End (with PDF)

```bash
# 1. Start backend
cd /home/user/.openclaw/workspace/paper-reproducibility
docker-compose up

# 2. Build agent image
docker build -f Dockerfile.agent -t paper-reproducibility-agent:latest .

# 3. Open browser
# http://localhost:5000

# 4. Upload a PDF (any PDF)
# Backend will:
# - Extract text
# - Ask Claude to find repos
# - Spawn agent containers
# - Stream progress to frontend

# 5. Watch agent execution in real-time
```

### Option 2: Quick Agent Test (without PDF)

```bash
# Build agent image
docker build -f Dockerfile.agent -t paper-reproducibility-agent:latest .

# Run agent on test repo
docker run \
  -e REPO_URL="https://github.com/kkirchheim/test-for-repro" \
  -e JOB_ID="test-manual-123" \
  -e BACKEND_URL="http://host.docker.internal:5000" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  paper-reproducibility-agent:latest

# Watch output - should see:
# - Repository cloned
# - Files discovered
# - Claude decisions
# - Commands executed (each printed with $)
# - Results logged
```

### Option 3: Direct Agent Testing (no backend needed)

```bash
# For debugging agent in isolation
docker run -it \
  -e REPO_URL="https://github.com/kkirchheim/test-for-repro" \
  -e JOB_ID="debug-123" \
  -e BACKEND_URL="http://localhost:9999" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  paper-reproducibility-agent:latest

# Agent will fail API calls (backend not running) but you'll see:
# - Git clone working
# - Files listed
# - Command execution
# - All debug output
```

## What to Look For

### Agent Output Format

**Command Execution:**
```
🔷 $ python iris_classification.py
======================================================================
Iris Flower Classification Experiment
======================================================================
...
✓ Test Accuracy: 0.9333 (93.33%)
```

**Logging:**
```
🔵 [INFO] Executing: pip install numpy
🟢 ✓ Command succeeded
🔴 ✗ Command failed (exit code 1)
```

**Progress to Backend:**
```
Sending: POST /api/agent/log
{
  "job_id": "...",
  "message": "Executing: python main.py",
  "severity": "info"
}
```

### Success Indicators

✅ **Agent started:** Prints "🦞 Paper Reproducibility Agent Starting"
✅ **Clone worked:** "✓ Repository cloned successfully"
✅ **Files found:** "📁 Found N files in repo root"
✅ **Claude decision:** "Action: read_file / run_command / done"
✅ **Command executed:** "$  <command>" printed
✅ **Output captured:** stdout/stderr printed
✅ **Progress logged:** "Sending to backend: /api/agent/log"

## Key Security Features

✅ **Execution in sandbox only**
```python
# Agent runs in container, never on host
subprocess.run(command, cwd="/workspace/repo", ...)
```

✅ **Path traversal prevention**
```python
# Can't escape repo directory
if not full_path.resolve().is_relative_to(repo_root):
    raise SecurityError("No path traversal!")
```

✅ **Resource limits**
```
- Memory: 2GB max
- CPU: 2 cores max
- Timeout: 300 seconds per command
- Auto-cleanup on exit
```

✅ **Every command printed** (for debugging)
```
$ git clone ...
$ python setup.py install
$ python main.py
```

## Debugging Commands

### View Agent Image Details

```bash
# Check if image exists
docker images | grep agent

# Inspect image
docker image inspect paper-reproducibility-agent:latest

# View image size
docker images --format "{{.Repository}} {{.Size}}" | grep agent
```

### View Agent Container Logs

```bash
# List running containers
docker ps

# View logs (if container still running)
docker logs -f <container_id>

# View last container logs
docker ps -a  # Find last agent container
docker logs <container_id>
```

### Test Docker Connectivity

```bash
# From backend container
docker exec paper-reproducibility bash -c "docker ps"

# Should work if Docker socket is properly mounted
```

## Troubleshooting

### Agent Can't Reach Backend

**Symptom:** "Failed to log to backend" errors

**Check:**
```bash
# 1. Backend running?
curl http://localhost:5000/jobs

# 2. Correct BACKEND_URL?
echo $BACKEND_URL  # Should be http://host.docker.internal:5000

# 3. Docker socket mounted?
ls -la /var/run/docker.sock
```

### Docker Image Build Fails

**Symptom:** `docker build -f Dockerfile.agent` returns error

**Check:**
```bash
# Rebuild without cache
docker build --no-cache -f Dockerfile.agent -t agent:latest .

# Check Python image available
docker images python:3.11-slim

# Manual test
docker run -it python:3.11-slim bash
```

### Agent Timeout

**Symptom:** "Command timed out after 300s"

**Fix:**
```python
# In agent.py, increase if needed
COMMAND_TIMEOUT = 600  # 10 minutes instead of 5
```

## Architecture Summary

```
┌─────────────────────────────────────┐
│ Backend (app.py)                    │
│ ├─ /upload PDF                      │
│ ├─ /api/agent/think (Claude)        │
│ ├─ /api/agent/log (progress)        │
│ └─ /events (SSE to frontend)        │
└────────────┬────────────────────────┘
             │ docker.containers.run()
             │
┌────────────▼────────────────────────┐
│ Agent Docker Container              │
│ ├─ agent.py                         │
│ ├─ /workspace/repo (cloned)         │
│ ├─ All execution here               │
│ └─ Communicates via HTTP            │
└────────────┬────────────────────────┘
             │
             └─ POST /api/agent/think ──→ Claude asks
             └─ POST /api/agent/log ──→ Progress shown
```

## Next Steps

1. **Test with test-for-repro**
   ```bash
   # Full end-to-end with real repo
   docker-compose up
   # Upload any PDF
   # Watch agent clone and run test-for-repro
   ```

2. **Add more test repos**
   - ML project (TensorFlow)
   - Data science (pandas)
   - Node.js project

3. **Implement Chunk 4: Result Aggregation**
   - Parse agent output
   - Extract metrics
   - Compare to paper
   - Generate reproducibility score

## Files at a Glance

| File | Purpose | Lines |
|------|---------|-------|
| `agent.py` | Agent script | ~400 |
| `Dockerfile.agent` | Sandbox image | 20 |
| `app.py` | Backend (modified) | +200 |
| `STAGE2_IMPLEMENTATION.md` | Full docs | ~400 |

## Commands Reference

```bash
# Build
docker build -f Dockerfile.agent -t paper-reproducibility-agent:latest .

# Run with backend
docker run \
  -e REPO_URL="..." \
  -e JOB_ID="..." \
  -e BACKEND_URL="http://host.docker.internal:5000" \
  -e ANTHROPIC_API_KEY="..." \
  paper-reproducibility-agent:latest

# Run without backend (debug)
docker run \
  -e REPO_URL="..." \
  -e JOB_ID="..." \
  -e BACKEND_URL="http://localhost:9999" \
  -e ANTHROPIC_API_KEY="..." \
  -it paper-reproducibility-agent:latest

# View logs
docker logs <container_id>

# Cleanup
docker container prune -f
docker image prune -f
```

---

**Ready to test!** Start with Option 1 or 2 above.
