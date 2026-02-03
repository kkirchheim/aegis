# Architecture - Paper Reproducibility Checker

## Overview

This document outlines the technical architecture of the Paper Reproducibility Checker system.

## System Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Browser / Frontend                          │
│  (HTML/CSS/JS + Server-Sent Events Client)                 │
│  ├─ Upload Form                                             │
│  ├─ Progress Log (real-time via SSE)                       │
│  └─ Reproducibility Report Display                         │
└────────────┬────────────────────────────────────────────────┘
             │
          HTTP + SSE
             │
┌────────────▼────────────────────────────────────────────────┐
│         Flask Backend (app.py)                               │
│  ├─ PDF Upload Handler                                     │
│  ├─ SSE Event Broadcaster                                  │
│  ├─ Claude API Caller                                      │
│  ├─ Background Job Processor (threading)                   │
│  ├─ Agent API Endpoints                                    │
│  └─ SQLite Database Interface                              │
└────────────┬─────────────────────┬──────────────────────────┘
             │                     │
          Claude API          SQLite Database
             │                     │
        ┌────▼────────┐     ┌──────▼──────┐
        │ Anthropic   │     │  jobs       │
        │ LLM         │     │  artifacts  │
        │ (Claude)    │     │  reports    │
        └─────────────┘     └─────────────┘
             │
      Docker API (Docker Socket)
             │
┌────────────▼────────────────────────────────────────────────┐
│     Docker Container (Per-Job Agent Sandbox)                │
│  ├─ agent.py (LLM Agent)                                   │
│  ├─ Repository (cloned)                                    │
│  ├─ Execution environment                                  │
│  └─ HTTP client (calls backend API)                        │
└────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend (HTML/CSS/JavaScript)

**Responsibilities:**
- User PDF upload interface
- Real-time progress monitoring via SSE
- Report display
- Job history browsing

**Key Features:**
- Drag-and-drop file upload
- EventSource API for streaming updates
- Responsive design (works on mobile)
- Job history with search/filtering

**Files:**
- `templates/index.html` - Main UI
- `static/style.css` - Styling
- `static/app.js` - JavaScript logic

### Backend - Flask Server (app.py)

**Responsibilities:**
- Accept PDF uploads
- Orchestrate analysis pipeline
- Provide SSE stream for progress
- Expose API for agent
- Database management

**Key Endpoints:**

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Serve frontend |
| `/upload` | POST | Accept PDF upload |
| `/events/<job_id>` | GET | Stream progress via SSE |
| `/job/<job_id>` | GET | Get job status/report |
| `/jobs` | GET | List all jobs |
| `/api/agent/think` | POST | Agent calls: what should I do? |
| `/api/agent/log` | POST | Agent logs progress |

**Key Functions:**

1. **`upload_pdf()`** - Handle PDF upload
   - Validate file (size, format)
   - Save to disk
   - Create DB record
   - Start background thread

2. **`analyze_paper_background(job_id, pdf_path)`** - Main job processor
   - Extract PDF text
   - Call Claude to parse paper
   - Find code artifacts
   - Generate report
   - Emit events via SSE

3. **`parse_paper_with_claude(pdf_text)`** - LLM parsing
   - Send full PDF text to Claude
   - Claude extracts: artifacts, reproducibility aspects
   - Returns structured JSON

4. **`events(job_id)`** - SSE endpoint
   - Create event queue for connection
   - Send events as they're emitted
   - Keep connection open until job complete

### Backend - Agent API (app.py)

**Two endpoints for agent communication:**

1. **`POST /api/agent/think`** - Agent asks Claude
   - Receives: job_id + repo_state
   - Returns: action (read_file, run_command, check_success, done)
   - Claude reasons about what to do next
   - No direct API key in agent

2. **`POST /api/agent/log`** - Agent progress logging
   - Receives: job_id + message
   - Emits to frontend via SSE
   - User sees live agent actions

### Docker Agent (agent.py)

**Runs inside container. Responsibilities:**
- Clone repository from URL
- Read files (README, requirements, etc.)
- Execute shell commands
- Call backend API to ask Claude
- Handle errors and report status

**Agent Loop:**
```
1. Clone repo from REPO_URL
2. List files in repo
3. Loop (max 15 iterations):
   a. Call backend: POST /api/agent/think
   b. Claude returns action
   c. Execute action:
      - read_file: Read and send file content
      - run_command: Execute shell command
      - check_success: Confirm success
      - done: Finished
   d. If error, loop continues (Claude suggests fix)
4. Exit when: done/error/max iterations
```

**Environment Variables:**
- `REPO_URL` - GitHub repo to analyze
- `JOB_ID` - Job ID (for API calls)
- `BACKEND_URL` - Backend server URL (e.g., http://host.docker.internal:5000)
- `ANTHROPIC_API_KEY` - Not passed to agent (backend has it)

### Database (SQLite)

**Schema:**

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,           -- UUID
    status TEXT,                   -- pending, processing, completed, error
    pdf_path TEXT NOT NULL,        -- Path to uploaded PDF
    pdf_filename TEXT,             -- Original filename
    report JSON,                   -- Final reproducibility report
    error_message TEXT,            -- Error details if failed
    created_at TIMESTAMP,          -- When job was created
    completed_at TIMESTAMP         -- When job finished
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY,        -- Auto-increment ID
    job_id TEXT,                   -- FK to jobs
    url TEXT,                      -- GitHub link, dataset URL, etc.
    artifact_type TEXT,            -- github_repo, dataset, docker, etc.
    description TEXT               -- What this artifact is
);
```

## Data Flow

### 1. PDF Upload Flow

```
User clicks "Upload PDF"
    ↓
Frontend: POST /upload (PDF file)
    ↓
Backend:
  - Validate file (size, format)
  - Save to uploads/{job_id}.pdf
  - Create Job record (status: pending)
  - Start background thread
    ↓
Return: { job_id: "...", message: "Analysis starting..." }
    ↓
Frontend receives job_id
Frontend: GET /events/{job_id} (opens SSE connection)
    ↓
SSE stream opened (waits for events)
```

### 2. Analysis Flow

```
Background thread runs: analyze_paper_background(job_id)
    ↓
1. Extract PDF text
   emit_event(job_id, {step: "extracting_pdf", message: "..."})
    ↓
2. Call Claude to parse paper
   - Prompt includes full PDF text
   - Claude extracts artifacts + reproducibility aspects
   emit_event(job_id, {step: "parsing_complete", artifacts: [...]})
    ↓
3. For each artifact (Phase 2):
   - Spin up Docker container
   - Pass REPO_URL, JOB_ID, BACKEND_URL to agent
   - Agent runs and makes decisions
    ↓
4. Aggregate results into report
   emit_event(job_id, {step: "complete", report: {...}})
    ↓
Frontend (via SSE):
  - Receives each event
  - Updates progress bar
  - Appends to live log
  - On "complete": displays report
```

### 3. Agent Loop Flow

```
Agent starts in Docker container
    ↓
1. Clone repository: git clone {REPO_URL}
    ↓
2. List files in repo root
    ↓
3. Agent iteration (max 15):
   a. Ask backend: POST /api/agent/think
      Body: { job_id, repo_state }
        ↓
      Backend calls Claude with repo state:
      - What files are here?
      - What was the last command output?
      - What should I do next?
        ↓
      Claude returns: {
        action: "read_file|run_command|check_success|done",
        target: "path or command",
        reasoning: "why"
      }
    ↓
   b. Agent executes action:
      - read_file: Read and store content
      - run_command: Execute shell, capture output/error
      - check_success: Confirm execution worked
      - done: Finished, exit loop
    ↓
   c. Update repo_state with new information
      (stdout, stderr, files changed, errors)
    ↓
   d. Agent logs: POST /api/agent/log
      Backend emits to frontend SSE
        ↓
4. Loop continues or exits based on action
```

## Event Flow (SSE)

Frontend opens persistent HTTP connection to `/events/{job_id}`:

```
GET /events/abc123

Server sends (continuous stream):
event: (empty)
data: {"step": "extracting_pdf", "message": "...", "progress": 10}

event: (empty)
data: {"step": "parsing_complete", "artifacts": [...], "progress": 40}

event: (empty)
data: {"step": "complete", "report": {...}, "progress": 100}

(connection closes)
```

Frontend JavaScript:
```javascript
const es = new EventSource("/events/abc123");
es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    // Update UI with data
};
```

## Phase Breakdown

### Phase 1: PDF Parsing (✅ Current)
- User uploads PDF
- Extract text with pdfplumber
- Call Claude to parse
- Find code artifacts
- Display report with findings

**New In Phase 1:**
- `POST /upload` endpoint
- `GET /events/<job_id>` SSE stream
- PDF text extraction
- Claude artifact parsing
- Frontend display

### Phase 2: Agent Execution (⏳ Next)
- Docker container management
- Agent loop implementation
- Agent-Backend API communication
- Code execution in sandbox
- Result aggregation

**Additions for Phase 2:**
- `agent.py` script
- `POST /api/agent/think` endpoint
- `POST /api/agent/log` endpoint
- Docker container spawning
- Agent error recovery

### Phase 3: Reproducibility Scoring
- Custom reproducibility aspects
- Result matching (output vs paper)
- Advanced reporting
- Extensible check system

### Phase 4: Production Deployment
- Authentication
- Rate limiting
- Monitoring/logging
- Horizontal scaling
- HTTPS/security hardening

## Technical Decisions

### Why SSE Instead of WebSocket?
- ✅ Simpler (built on HTTP)
- ✅ Works with older browsers
- ✅ Less infrastructure
- ✅ Easier debugging
- ❌ One-way only (good enough for progress)

### Why Threading Instead of Celery?
- ✅ Simpler for MVP (no external queue)
- ✅ No Redis dependency
- ✅ Easier local development
- ✅ Sufficient for small deployments
- ❌ Won't scale to 100+ jobs
- *Upgrade to Celery + Redis in Phase 4*

### Why Agent Calls Backend for Claude?
- ✅ API key never leaves backend
- ✅ Security (container compromise doesn't expose key)
- ✅ Easy to audit/log Claude calls
- ✅ Rate limiting on backend
- ❌ Extra network round-trip (acceptable: seconds per decision)

### Why SQLite?
- ✅ Simple, no setup
- ✅ Good for MVP
- ✅ Single file (easy backup)
- ❌ Won't handle concurrent writes well
- *Upgrade to PostgreSQL in Phase 4*

## Deployment Considerations

### Development
- Local machine
- Docker Compose with volumes
- Live code reload

### Production (Future)
- Kubernetes or Docker Swarm
- PostgreSQL instead of SQLite
- Redis for sessions/caching
- Celery workers
- Nginx reverse proxy
- SSL/TLS
- API key management (Vault/Secrets Manager)

## Security Model

### API Key Protection
- Never stored in code ✅
- Environment variable only ✅
- Not passed to agent ✅
- Backend isolates it ✅

### Docker Sandbox Isolation
- Resource limits (2GB RAM, 2 CPU)
- Network isolation (no internet)
- Filesystem isolation (read-only system)
- Automatic cleanup

### File Upload Safety
- Size limit (100MB)
- Format validation (.pdf only)
- Stored with UUID names
- Not accessible via web

## Performance

### Optimizations
- SSE streaming (no polling)
- Threading for background jobs
- PDF text truncation (8K tokens max)
- File content caching in agent
- Container resource limits

### Metrics to Monitor (Phase 4)
- Job processing time (P50, P95, P99)
- PDF extraction latency
- Claude API call latency
- Container startup time
- Memory usage per job
- Error rate by job type

## Testing Strategy

### Unit Tests
- PDF extraction
- Claude response parsing
- File read/write operations
- Database queries

### Integration Tests
- Full upload-to-report flow
- Agent loop execution
- SSE streaming
- Error handling

### End-to-End Tests
- Upload real papers
- Verify artifact detection
- Check report accuracy

See `tests/` directory for test files.

## Future Improvements

1. **Batch Processing** - Analyze multiple papers
2. **Advanced Checks** - Custom reproducibility criteria
3. **Result Comparison** - Auto-match output to paper
4. **Visualization** - Charts, trends, comparisons
5. **Collaboration** - Share reports, comments
6. **CI/CD Integration** - GitHub Actions for papers
7. **Public APIs** - Allow external tools to use checker
8. **Web Hooks** - Notify on completion

---

**Last Updated:** February 3, 2026  
**Status:** Phase 1 (PDF Parsing)  
**Maintainer:** @konstantin
