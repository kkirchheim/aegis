# Agent Container Configuration

## Overview

The Agent runs in a Docker container to safely execute arbitrary repository code in an isolated environment. The container has been hardened for security and reliability.

## Container Improvements (Session 13+)

### Before
```dockerfile
FROM python:3.11-slim
# - Running as root (security risk, permission issues)
# - No virtual environment (global pip conflicts)
# - Minimal image (missing dependencies)
```

### After
```dockerfile
FROM python:3.11  # Fuller image, better compatibility
# - Non-root user (security best practice)
# - Python virtual environment (isolated deps)
# - System build tools included (compiled packages work)
# - Git LFS support (large file handling)
```

## Key Features

### 1. Non-Root User
```dockerfile
RUN groupadd -r agent && useradd -r -g agent agent
USER agent
```

**Why it matters:**
- ✅ Security: Non-root can't modify host system
- ✅ Permission ownership: Files created as `agent:agent`, not `root:root`
- ✅ Docker best practice: Least privilege principle

**Before:** Downloaded packages owned by `root`, causing permission conflicts
**After:** Packages owned by `agent` user, clean isolation

### 2. Python Virtual Environment
```dockerfile
ENV VENV=/home/agent/venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir requests
```

**Why it matters:**
- ✅ Isolation: Agent dependencies don't conflict with system Python
- ✅ Cleanliness: Fresh environment for each code execution
- ✅ Best practice: Standard Python development approach

**Before:** Global `pip install` could conflict with system packages
**After:** Isolated venv prevents conflicts

### 3. Full Python Image
```dockerfile
FROM python:3.11  # (not python:3.11-slim)
```

Includes:
- Build tools (gcc, make, etc.) - needed for numpy, scipy compilation
- Development headers - required for C extensions
- libssl/ca-certificates - for SSL/TLS connections

**Before:** slim image missing `build-essential`, causing package installation failures
**After:** Full image with all needed compilation tools

### 4. System Dependencies
```dockerfile
RUN apt-get install -y \
    git \                # Clone repos
    git-lfs \            # Handle large files
    curl \               # Fetch resources
    build-essential \    # C compilation
    python3-dev \        # Python development headers
    ca-certificates      # SSL/TLS for pip
```

## How Agent Executes Code

### 1. Container Spawned
```python
# Backend spawns agent container
docker_client.containers.run(
    "paper-reproducibility-agent:latest",
    detach=True,
    environment={
        "REPO_URL": "https://github.com/...",
        "JOB_ID": "...",
        "BACKEND_URL": "..."
    }
)
```

### 2. Agent Initializes (in virtual environment)
```bash
$ python /app/agent.py
# PATH is: /home/agent/venv/bin:/usr/local/sbin:/usr/local/bin:...
# python/pip use venv automatically
```

### 3. Agent Clones & Executes
```bash
$ git clone $REPO_URL /workspace/repo
$ cd /workspace/repo
$ pip install -r requirements.txt  # Installs to /home/agent/venv
$ python script.py                 # Runs with venv Python
```

### 4. Output Reported
```bash
$ curl http://paper-reproducibility:5000/api/agent/think
# Gets decision from Claude
# Executes command
# Reports result
```

## Security Implications

### Process Isolation
```bash
# Before: Running as root
docker run python:3.11-slim python /app/agent.py
# ⚠️ Process: root
# ⚠️ Can modify /etc, /sys, etc.

# After: Running as agent user
docker run paper-reproducibility-agent:latest
# ✅ Process: agent (uid 1000+)
# ✅ Can only modify /workspace, /home/agent
```

### File Ownership
```bash
# Before: Root-owned files
-rw-r--r-- root root numpy-2.4.2.whl

# After: Agent-owned files
-rw-r--r-- agent agent numpy-2.4.2.whl
# Cleanup: agent user can delete its own files
```

### Virtual Environment Isolation
```bash
# Before: Global Python packages
/usr/local/lib/python3.11/site-packages/
# Package A version 1.0 installed globally
# Agent repo needs version 2.0 → CONFLICT

# After: Isolated venv
/home/agent/venv/lib/python3.11/site-packages/
# Package A version 2.0 installed in venv
# System packages untouched
```

## Rebuilding the Container

After changes to `Dockerfile.agent`:

```bash
cd /home/user/.openclaw/workspace/paper-reproducibility

# Remove old image
docker rmi paper-reproducibility-agent:latest

# Rebuild
docker build -f Dockerfile.agent -t paper-reproducibility-agent:latest .

# Verify
docker run --rm paper-reproducibility-agent:latest python -c "import sys; print(sys.prefix)"
# Should output: /home/agent/venv
```

## Testing the Improvement

### Verify Non-Root User
```bash
docker run --rm paper-reproducibility-agent:latest whoami
# Output: agent
```

### Verify Virtual Environment
```bash
docker run --rm paper-reproducibility-agent:latest python -c "import sys; print(sys.prefix)"
# Output: /home/agent/venv
```

### Verify Build Tools
```bash
docker run --rm paper-reproducibility-agent:latest which gcc make
# Output: /usr/bin/gcc /usr/bin/make
```

### Test with Real Package Installation
```bash
docker run --rm paper-reproducibility-agent:latest pip install numpy scipy scikit-learn --quiet && python -c "import numpy; print(numpy.__version__)"
# Should successfully compile and import
```

## Common Issues

### Issue: "Permission denied" when cloning
**Before Fix:**
- Agent runs as root, creates files as `root:root`
- Later container runs as `agent`, can't overwrite root-owned files

**After Fix:**
- Agent runs as `agent`, creates files as `agent:agent`
- Clean ownership, no permission conflicts

### Issue: "pip: command not found"
**Before Fix:**
- Slim image might not have pip or build tools

**After Fix:**
- Full image includes pip and build-essential
- Virtual environment installed in every container

### Issue: Compiled packages fail (numpy CPU optimization)
**Before Fix:**
- Missing build tools meant numpy not rebuilt from source
- Falls back to binary wheel incompatible with system

**After Fix:**
- `build-essential` + `python3-dev` means packages can compile
- Can create CPU-specific optimized binaries

## Future Improvements

### Consider:
1. **Add caching layer** - Pre-cache common packages (numpy, scipy, scikit-learn)
2. **Multi-stage build** - Reduce final image size (~600MB → ~300MB)
3. **Security scanning** - CVE checks on base image
4. **Resource limits** - Enforce memory/CPU limits per container
5. **Container signing** - GPG sign agent image for verification

## References

- Docker Security Best Practices: https://docs.docker.com/engine/security/
- Python Virtual Environments: https://docs.python.org/3/tutorial/venv.html
- Dockerfile Best Practices: https://docs.docker.com/develop/dev-best-practices/dockerfile_best-practices/
