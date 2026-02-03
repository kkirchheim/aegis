# Project Setup - Paper Reproducibility Checker

## Quick Reference

- **GitHub Repository:** https://github.com/kkirchheim/paper-reproducibility (private)
- **Local Path:** `/home/user/.openclaw/workspace/paper-reproducibility`
- **Tech Stack:** Flask + Claude API + Docker + React-less frontend
- **Current Phase:** Phase 1 (PDF parsing) ✅
- **Next Phase:** Phase 2 (Docker agent execution)

## Repository Structure

```
paper-reproducibility/
├── README.md                    # Getting started guide
├── ARCHITECTURE.md              # Technical design & flow
├── API.md                       # API reference (all endpoints)
├── PROJECT_SETUP.md             # This file
├── LICENSE                      # MIT License
│
├── app.py                       # Flask backend (main server)
├── agent.py                     # LLM agent (runs in Docker containers)
│
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container image
├── docker-compose.yml           # Multi-container setup
│
├── templates/
│   └── index.html              # Frontend HTML
├── static/
│   ├── app.js                  # Frontend JavaScript
│   └── style.css               # Frontend styling
│
├── uploads/                     # PDF storage (created at runtime)
├── logs/                        # Application logs (created at runtime)
├── reproducibility.db           # SQLite database (created at runtime)
│
└── .env.example                # Environment variables template
```

## File Purposes

### Core Application

| File | Purpose | Language |
|------|---------|----------|
| `app.py` | Flask backend, PDF upload, SSE stream, Claude API calls | Python |
| `agent.py` | LLM agent for Docker containers, repo analysis | Python |
| `requirements.txt` | Python dependencies (Flask, Anthropic, pdfplumber, Docker SDK) | Text |

### Frontend

| File | Purpose |
|------|---------|
| `templates/index.html` | Main UI (upload form, progress log, report display) |
| `static/app.js` | JavaScript (upload handler, SSE client, DOM updates) |
| `static/style.css` | Responsive styling (purple theme, log styling) |

### Configuration & Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local dev setup (Flask + Docker socket) |
| `Dockerfile` | Container image (Python 3.10 + dependencies) |
| `.env.example` | Environment variable template |
| `.gitignore` | Git ignore rules |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Quick start, features, usage |
| `ARCHITECTURE.md` | Technical design, data flow, phase breakdown |
| `API.md` | HTTP endpoint reference |
| `PROJECT_SETUP.md` | This file |
| `LICENSE` | MIT License |

## Key Decisions Documented

### 1. Technology Choices

- **Backend:** Flask (simple, familiar)
  - Could scale to FastAPI/async later
  
- **Communication:** Server-Sent Events (SSE)
  - Simpler than WebSocket for MVP
  - Good enough for one-way progress updates
  
- **Job Processing:** Threading
  - Simple for MVP (no external queue)
  - Upgrade to Celery + Redis in Phase 4
  
- **Database:** SQLite
  - No setup needed
  - Upgrade to PostgreSQL for multi-server
  
- **LLM:** Claude (Anthropic)
  - Fast, powerful, good for reasoning
  - Agent calls backend API (key never in container)

### 2. Architecture Patterns

- **Agent Autonomy:** Agent asks Claude for each decision
  - Claude sees repo state, suggests action
  - Agent executes, reports back
  
- **Security:** API key never leaves Flask process
  - Agent calls backend HTTP API
  - Container compromise doesn't expose key
  
- **Simplicity:** No external dependencies for MVP
  - Redis only if needed (Phase 4)
  - All job state in DB
  
- **Real-time:** SSE streaming
  - Frontend gets live updates without polling
  - Easier debugging than WebSocket

### 3. Phase Breakdown

**Phase 1 (✅ Complete):**
- PDF upload
- Text extraction
- Claude parsing (artifacts + reproducibility aspects)
- SSE progress stream
- Report display

**Phase 2 (⏳ Next):**
- Docker container spawning
- Agent loop execution
- Agent-backend API communication
- Code execution in sandbox
- Result aggregation

**Phase 3 (Future):**
- Advanced reproducibility checks
- Custom scoring system
- Result matching
- Extended reporting

**Phase 4 (Future):**
- Authentication
- Production deployment
- Scaling (Celery, PostgreSQL, Redis)
- Monitoring
- Public APIs

## Database Schema

### Table: `jobs`
Tracks analysis jobs

| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT PRIMARY KEY | UUID, e.g., "550e8400-e29b-41d4-a716-446655440000" |
| `status` | TEXT | pending, processing, completed, error |
| `pdf_path` | TEXT | File path on disk (e.g., "uploads/550e8400-e29b-41d4-a716-446655440000.pdf") |
| `pdf_filename` | TEXT | Original filename from upload |
| `report` | JSON | Reproducibility report (parsed artifacts, findings) |
| `error_message` | TEXT | Error details if failed |
| `created_at` | TIMESTAMP | When job was submitted |
| `completed_at` | TIMESTAMP | When job finished |

### Table: `artifacts`
Code artifacts found in papers

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-increment |
| `job_id` | TEXT FK | Links to `jobs.id` |
| `url` | TEXT | GitHub, dataset, or other URL |
| `artifact_type` | TEXT | github_repo, dataset, docker, supplementary |
| `description` | TEXT | What this artifact is |

## API Summary

See `API.md` for complete documentation.

### Upload & Monitor Flow

1. `POST /upload` - Upload PDF
2. `GET /events/<job_id>` - Stream progress (SSE)
3. `GET /job/<job_id>` - Get final report

### Agent Communication (Internal)

1. `POST /api/agent/think` - Agent asks Claude what to do
2. `POST /api/agent/log` - Agent reports progress

### Info Endpoints

- `GET /` - Frontend
- `GET /jobs` - List all jobs

## Development Workflow

### Setup

```bash
# Clone repo
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

# Copy env template
cp .env.example .env

# Add API key to .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```

### Running

```bash
# Option 1: Docker Compose (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."
docker-compose up

# Option 2: Local Python
export ANTHROPIC_API_KEY="sk-ant-..."
pip install -r requirements.txt
python app.py
```

### Testing

```bash
# Test upload (local or Docker)
curl -X POST \
  -F "pdf=@test.pdf" \
  http://localhost:5000/upload

# Test SSE stream
curl -N http://localhost:5000/events/job-id-here

# List jobs
curl http://localhost:5000/jobs
```

## Code Navigation

### Key Functions in `app.py`

| Function | Purpose | Lines |
|----------|---------|-------|
| `init_db()` | Create database schema | ~20 |
| `emit_event(job_id, event)` | Emit SSE event to all clients | ~10 |
| `extract_pdf_text(pdf_path)` | Extract text from PDF | ~15 |
| `parse_paper_with_claude(pdf_text)` | Call Claude to parse paper | ~35 |
| `upload_pdf()` | Handle POST /upload | ~30 |
| `events(job_id)` | Handle GET /events/{job_id} (SSE) | ~25 |
| `analyze_paper_background(job_id)` | Main background job | ~60 |
| `agent_think()` | POST /api/agent/think endpoint | ~30 |
| `agent_log()` | POST /api/agent/log endpoint | ~15 |

### Key Functions in `agent.py`

| Function | Purpose |
|----------|---------|
| `ask_claude_what_to_do()` | Call backend /api/agent/think |
| `run_shell_command(cmd)` | Execute shell command, capture output |
| `read_file(filepath)` | Read file safely (within repo) |
| `list_files(directory)` | List files in directory |
| `agent_loop()` | Main agent loop (15 iterations max) |

### Frontend JavaScript (`static/app.js`)

| Function | Purpose |
|----------|---------|
| `uploadPaper()` | Handle PDF upload |
| `connectSSE(job_id)` | Open SSE connection |
| `handleProgressEvent(event)` | Process SSE event |
| `displayReport(report)` | Render report HTML |
| `loadJobsHistory()` | Fetch and display previous jobs |
| `viewJob(job_id)` | Load and display specific job |

## Debugging Tips

### Check if backend is running
```bash
curl http://localhost:5000/jobs
```

### Monitor logs
```bash
# Docker
docker-compose logs -f app

# Local
# Check console output (Flask debug output)
```

### Check database
```bash
sqlite3 reproducibility.db "SELECT * FROM jobs;"
```

### Test SSE stream
```bash
# In one terminal (upload)
curl -X POST -F "pdf=@paper.pdf" http://localhost:5000/upload

# In another (monitor with job_id)
curl -N http://localhost:5000/events/job-id-from-above
```

## Common Issues

### "ANTHROPIC_API_KEY not set"
```bash
# Solution: Export it
export ANTHROPIC_API_KEY="sk-ant-..."

# Or in Docker Compose .env:
ANTHROPIC_API_KEY=sk-ant-...
```

### Port 5000 in use
```bash
# Find process using port
lsof -i :5000

# Or use different port
docker-compose up -e FLASK_PORT=5001
```

### Docker socket not accessible
```bash
# Check if Docker daemon is running
docker ps

# Fix permissions (add user to docker group)
sudo usermod -aG docker $USER
newgrp docker
```

### PDF extraction fails
- Check PDF format (must be valid PDF)
- Check file size (max 100MB)
- Some PDFs might be image-based (OCR needed in Phase 3)

## Next Implementation Steps (Phase 2)

1. **Docker Agent Integration**
   - Build agent Docker image
   - Implement container spawning in Flask
   - Test agent loop with mock repos

2. **Agent-Backend Communication**
   - Test /api/agent/think endpoint
   - Test /api/agent/log progress reporting
   - Handle errors and retries

3. **Container Management**
   - Resource limits (2GB RAM, 2 CPU)
   - Timeout handling (10 min max)
   - Cleanup on completion/error

4. **Testing**
   - Test with real GitHub repos
   - Test error scenarios
   - Test timeout scenarios

## Useful Commands

```bash
# Start fresh
rm reproducibility.db uploads/*.pdf

# View git log
git log --oneline -5

# Check uncommitted changes
git status

# View current branch
git branch -a

# Commit changes
git add -A
git commit -m "message"
git push origin master

# View code stats
wc -l app.py agent.py

# Format code
black app.py agent.py
```

## Git Workflow

```bash
# Clone
git clone https://github.com/kkirchheim/paper-reproducibility.git

# Make changes
# ... edit files ...

# Commit locally
git add app.py
git commit -m "Fix: handle missing README gracefully"

# Push to GitHub
git push origin master

# Check status
git log --oneline -3
```

## Documentation Files

- **README.md** - User-facing, getting started
- **ARCHITECTURE.md** - Technical deep dive, data flow, phases
- **API.md** - HTTP endpoint reference
- **PROJECT_SETUP.md** - This file, project structure & navigation
- Code comments - Implementation details

Read ARCHITECTURE.md for technical understanding.  
Read API.md for endpoint details.  
Read README.md for user instructions.

---

**Status:** Phase 1 Complete ✅  
**Last Updated:** February 3, 2026  
**Next Phase:** Phase 2 - Docker Agent Execution
