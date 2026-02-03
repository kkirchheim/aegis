# Development Guide

Setup, testing, and development practices for contributors.

## Local Setup

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Anthropic API key
- Git

### Quick Start

```bash
# Clone repository
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

Visit `http://localhost:5000`

### Alternative: Local Python

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run Flask
python app.py
```

Visit `http://localhost:5000`

---

## Project Structure

```
paper-reproducibility/
├── app.py                    # Flask backend
├── agent.py                  # Docker agent
├── requirements.txt          # Python dependencies
├── Dockerfile                # Flask container
├── Dockerfile.agent          # Agent sandbox container
├── docker-compose.yml        # Multi-container setup
├── reproducibility.db        # SQLite (auto-created)
├── templates/
│   ├── index.html           # Home page
│   └── detail.html          # Report page
├── static/
│   ├── app.js               # Frontend logic
│   ├── detail.js            # Report logic
│   └── style.css            # Minimal styles
├── tests/
│   └── test_agent_api.py   # Test suite
├── docs/                    # Documentation
│   ├── API.md              # API reference
│   ├── ARCHITECTURE.md     # System design
│   ├── DEVELOPMENT.md      # This file
│   ├── DEPLOYMENT.md       # Production
│   ├── TROUBLESHOOTING.md  # Debugging
│   └── CHANGELOG.md        # Version history
└── README.md               # Project overview
```

---

## Testing

### Run Full Test Suite

```bash
# Using Docker Compose (recommended)
docker-compose exec app pytest tests/ -v

# Or with direct Python
pytest tests/test_agent_api.py -v

# With coverage
pytest tests/ --cov=app
```

### Test Organization

**TestAgentThink** - `/api/agent/think` endpoint
- Valid requests work
- Handles None values
- Manages large outputs
- Escapes special characters

**TestAgentLog** - `/api/agent/log` endpoint
- Message logging works
- Handles large messages
- Validates job_id

**TestPrompBuilding** - Claude prompt construction
- Context truncation works
- Large outputs don't crash

### Adding Tests

New tests for bug fixes:

```python
class TestNewFeature:
    """Tests for new feature"""
    
    def test_basic_functionality(self, client):
        """Happy path - should work."""
        response = client.post('/api/endpoint', json={...})
        assert response.status_code == 200
    
    def test_none_handling(self, client):
        """Edge case - None values shouldn't crash."""
        response = client.post('/api/endpoint', json={"field": None})
        assert response.status_code != 500
    
    def test_very_large_input(self, client):
        """Stress test - large data."""
        response = client.post('/api/endpoint', json={"field": "x" * 10000})
        assert response.status_code in [200, 400]
```

Key principle: Test failures before fixes.

---

## Agent Container (Docker)

The agent runs isolated in a Docker container for safety and reproducibility.

### Container Improvements

**Image: `FROM python:3.11`** (not `-slim`)
- Includes build tools (gcc, make)
- Development headers for C extensions
- SSL/TLS certificates
- Git + curl + build-essential

**Features:**
- Non-root `agent` user (security)
- Python virtual environment (isolation)
- Auto-cleanup on exit
- Resource limits (2GB RAM, 2 CPU)

### Agent Execution

```bash
# Spawn agent for a job
docker run \
  --rm \
  --memory="2g" \
  --cpus="2" \
  -e REPO_URL="https://github.com/..." \
  -e JOB_ID="abc123" \
  -e BACKEND_URL="http://host.docker.internal:5000" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  paper-reproducibility-agent:latest
```

### Key Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `REPO_URL` | Repository to analyze | `https://github.com/user/repo` |
| `JOB_ID` | Job identifier | `abc-123-def` |
| `BACKEND_URL` | Backend API URL | `http://paper-reproducibility:5000` |
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |

### Agent Communication

Agent only communicates via HTTP (no shell access to host):

```python
# Agent asks: What should I do?
POST /api/agent/think {
  "job_id": "abc123",
  "repo_state": {...}
}

# Backend responds with Claude's decision
{
  "action": "read_file | run_command | check_success | done",
  "target": "path or command",
  "reasoning": "why"
}

# Agent logs progress
POST /api/agent/log {
  "job_id": "abc123",
  "message": "Reading README.md"
}

# Agent submits execution details
POST /api/agent/execution {
  "job_id": "abc123",
  "commands_run": "...",
  "stdout_combined": "...",
  "actual_results": {...},
  "dependencies_used": "...",
  "errors_summary": "..."
}

# Agent reports completion
POST /api/agent/complete {
  "job_id": "abc123",
  "success": true,
  "message": "...",
  "accuracy": 0.93,
  "reproducibility_aspects": {...}
}
```

---

## Code Style

### Format & Lint

```bash
# Format code
black app.py agent.py tests/

# Check style
flake8 app.py agent.py tests/ --max-line-length=120

# Type checking
mypy app.py --ignore-missing-imports
```

### Conventions

- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Line length: 120 characters
- Docstrings: Google style

### Comments

```python
# Bad: Obvious comments
x = 5  # Set x to 5

# Good: Explain why, not what
# Use 5 iterations to balance accuracy vs performance
MAX_ITERATIONS = 5

# Good: Complex logic needs explanation
# SQLite doesn't support UPSERT, so check then insert
if not user_exists:
    insert_user(user)
```

---

## Debugging

### View Logs

```bash
# All service logs
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f paper-reproducibility

# Filter by pattern
docker-compose logs | grep "Claude Response"
```

### Check Database

```bash
# Connect to SQLite
sqlite3 reproducibility.db

# List tables
.tables

# View jobs
SELECT id, status, pdf_filename, created_at FROM jobs LIMIT 5;

# View a specific job's events
SELECT step, message, timestamp FROM events WHERE job_id='abc123' ORDER BY timestamp;
```

### Debug Flask App

```python
# In app.py
app.logger.debug(f"Debug message: {variable}")
app.logger.info(f"Info: {data}")
app.logger.warning(f"Warning: {issue}")
app.logger.error(f"Error: {error}", exc_info=True)
```

View in logs:
```bash
docker-compose logs -f | grep "DEBUG\|ERROR"
```

---

## Building & Deployment

### Build Docker Images

```bash
# Flask app image
docker-compose build app

# Agent sandbox image
docker-compose build paper-reproducibility

# Rebuild without cache
docker-compose build --no-cache
```

### Environment Configuration

Create `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-4-1
FLASK_ENV=development
FLASK_DEBUG=1
```

Load with Docker Compose (automatic via `.env`).

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Restart specific service
docker-compose restart app

# Full reset (removes volumes)
docker-compose down -v

# View resource usage
docker stats

# Clean up unused images
docker image prune -a
```

---

## Contributing Workflow

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes
4. Run tests: `pytest tests/ -v`
5. Format code: `black app.py`
6. Lint code: `flake8 app.py`
7. Commit: `git commit -m "Clear description"`
8. Push: `git push origin feature/my-feature`
9. Open Pull Request on GitHub

### Commit Message Format

```
<type>(<scope>): <subject>

<body (optional)>

<footer (optional)>
```

**Types:**
- feat: New feature
- fix: Bug fix
- docs: Documentation
- test: Test addition
- refactor: Code restructure
- perf: Performance improvement
- chore: Tooling/config change

**Examples:**
```
feat(agent): add determinism check
fix(api): handle None errors in repo_state
docs: clarify architecture diagram
test: add None value edge case tests
```

---

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = slow_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative').print_stats(10)
```

### Common Bottlenecks

| Issue | Symptom | Fix |
|-------|---------|-----|
| Large prompt | Slow Claude API | Truncate output to 2000 chars |
| DB queries | N+1 queries | Use `.all()` instead of loops |
| Docker startup | Slow first run | Pre-build image |
| Memory leak | Increasing RAM | Check for unreleased resources |

---

## FAQ for Developers

**Q: How do I add a new reproducibility aspect?**
A: Add to Claude prompt in `evaluate_reproducibility_aspects()`. Frontend renders dynamically.

**Q: How do I test a change locally?**
A: Run `docker-compose up`, upload PDF via browser, check logs/database.

**Q: How do I reset the database?**
A: `docker-compose down -v` (removes volumes), then `docker-compose up` recreates.

**Q: Why is my container exiting immediately?**
A: Check logs: `docker-compose logs app`. Usually missing env var or import error.

**Q: How do I debug the agent?**
A: Agent logs are emitted to SSE. Frontend shows them live. Also check: `docker-compose logs paper-reproducibility`.

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for more.
