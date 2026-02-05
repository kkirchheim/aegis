# System Architecture

Complete technical design of the Paper Reproducibility Checker.

## Table of Contents

- [Overview](#overview)
- [Three-Stage Pipeline](#three-stage-pipeline)
- [System Components](#system-components)
  - [Data Layer Architecture](#data-layer-architecture)
  - [Service Architecture](#service-architecture)
- [Real-Time Updates](#real-time-updates)
- [Data Flow](#data-flow)
- [Execution Model](#execution-model)
- [Networking](#networking)
- [Security](#security)
- [Performance](#performance)
- [Technology Stack](#technology-stack)

---

## Overview

Paper Reproducibility Checker is a web application that analyzes academic papers for reproducibility by:
1. Extracting and parsing PDF content
2. Executing paper code in sandboxed containers
3. Evaluating reproducibility across 15 dimensions

All components communicate via REST APIs. Event-driven architecture tracks progress via database polling.

---

## Three-Stage Pipeline

```
┌──────────────────────────────────────┐
│ STAGE 1: PAPER ANALYSIS              │
├──────────────────────────────────────┤
│ • Extract PDF text                   │
│ • Parse metadata (title, abstract)    │
│ • Extract citations                  │
│ • Identify code artifacts            │
│ → Store in PaperAnalysis model      │
└──────────────┬───────────────────────┘
               ↓
┌──────────────────────────────────────┐
│ STAGE 2: CODE EXECUTION              │
├──────────────────────────────────────┤
│ • Clone GitHub repositories          │
│ • Discover files and dependencies    │
│ • Execute main script in sandbox     │
│ • Capture output and results         │
│ → Store in ExecutionDetails model   │
└──────────────┬───────────────────────┘
               ↓
┌──────────────────────────────────────┐
│ STAGE 3: MULTI-SOURCE EVALUATION     │
├──────────────────────────────────────┤
│ • Claude evaluates 15 aspects        │
│ • Compares paper claims vs actual    │
│ • Generates evidence-based findings  │
│ → Store in AspectEvaluation models  │
└──────────────┬───────────────────────┘
               ↓
         Report Display
```

**Progress Ranges:**
- Stage 1: 0.0 → 0.33
- Stage 2: 0.33 → 0.66
- Stage 3: 0.66 → 1.0

---

## System Components

### Frontend
- **HTML Templates:** Upload form, report display, job history
- **CSS:** Tailwind + DaisyUI for professional UI
- **JavaScript:** Polling mechanism every 200ms via `/api/job/<id>/full`
- **Real-Time Updates:** Appended event log, dynamic section visibility

### Backend (Flask)
- **PDF Processing:** Extract text, extract metadata, cache results
- **LLM Interface:** Multi-provider abstraction (Anthropic, Ollama)
- **Agent Orchestration:** Spawn Docker containers, coordinate pipeline
- **Database:** SQLite with Peewee ORM (12 models)
- **Authentication:** User registration, session management

### Agent (Docker Container)
- **Repository Operations:** Clone repos, discover files
- **Code Execution:** Run scripts in sandbox, capture output
- **Backend Communication:** HTTP requests for decisions and logging

### External Services
- **Anthropic Claude API:** Paper parsing, artifact extraction, evaluation
- **GitHub:** Clone public repositories

---

## System Components

### Data Layer Architecture

#### Peewee ORM Overview
We use **Peewee** (lightweight ORM) for type-safe, testable database access:
- Replaces 25+ raw SQL calls with object-oriented models
- Automatic query generation and parameter binding
- Transaction support for multi-step operations
- Easy migrations and schema management

**Why Peewee:** Minimal dependencies, plays well with Flask, zero-boilerplate queries.

#### Database Models (12 total)

**Core Models:**
- `User` - User accounts (username, email, password_hash)
- `Job` - PDF analysis jobs (id, status, progress, pdf_path, report)

**Analysis Results:**
- `PaperAnalysis` - Stage 1: PDF extraction (title, abstract, citations, methodology)
- `ExecutionDetails` - Stage 2: Code execution (commands_run, stdout, actual_results)
- `AspectEvaluation` - Stage 3: Reproducibility aspects (15 evaluations per job)

**Supporting Models:**
- `Artifact` - Code artifacts discovered in papers (url, artifact_type)
- `Event` - Job events for tracking progress (step, message, stage_duration_ms)
- `ChatSession` - Interactive Q&A session per job
- `ChatMessage` - Messages in chat session (role, content, timestamp)

**Cache Models:**
- `CachePaperAnalysis` - Cached paper analysis by PDF hash
- `CacheCodeExecution` - Cached code execution by repo hash
- `CacheEvaluation` - Cached evaluations by paper+code hash

#### Repositories (11 total)

Pattern for consistent data access:
```python
# Each repository encapsulates queries for one model
repository.get(id)           # Get single item
repository.list_all()        # List all items
repository.create()          # Insert
repository.delete(id)        # Delete
```

**Core Repositories:**
1. `UserRepository` - User lookup, creation, password updates
2. `JobRepository` - Job CRUD, filtering by user
3. `PaperAnalysisRepository` - Stage 1 results lookup/store
4. `ExecutionDetailsRepository` - Stage 2 results lookup/store
5. `AspectEvaluationRepository` - Stage 3 results lookup/store
6. `ArtifactRepository` - Artifact discovery and lookup
7. `EventRepository` - Event storage and querying

**Cache Repositories:**
8. `CachePaperAnalysisRepository` - Cache lookup by PDF hash
9. `CacheCodeExecutionRepository` - Cache lookup by repo hash
10. `CacheEvaluationRepository` - Cache lookup by paper+code hash
11. `ChatSessionRepository` - Session management

---

### Service Architecture

#### Service Layer Overview

Services implement business logic and orchestrate repositories. Each service:
- Uses repositories for data access (no direct SQL)
- Emits events for state transitions
- Handles caching at appropriate layers
- Provides testable abstractions

#### Service Dependency Diagram

```
┌─────────────────────────────────────────────────────────┐
│ PipelineOrchestrator (MAIN ENTRY POINT)                │
│ run_analysis() → coordinates all 3 stages             │
└────────┬────────────────────────────────────────────────┘
         │
         ├─→ Stage 1: AnalysisService
         │   ├─→ extract_and_analyze_pdf()
         │   ├─→ CacheService (paper analysis cache)
         │   └─→ PaperAnalysisRepository
         │
         ├─→ Stage 2: DockerService  
         │   ├─→ spawn_agent_container()
         │   ├─→ CacheService (code execution cache)
         │   └─→ ExecutionDetailsRepository
         │
         ├─→ Stage 3: EvaluationService
         │   ├─→ evaluate_reproducibility_aspects()
         │   ├─→ CacheService (evaluation cache)
         │   └─→ AspectEvaluationRepository
         │
         └─→ EventDispatcher (ALL STAGES)
             ├─→ Persists events to Event table
             └─→ Updates Job status/progress/stage
```

#### Services Reference Table

| Service | Purpose | Key Responsibility |
|---------|---------|-------------------|
| `PipelineOrchestrator` | Coordinates 3-stage analysis | Run complete pipeline, emit stage transitions |
| `AnalysisService` | PDF extraction & parsing | Extract text, call Claude for metadata/artifacts |
| `DockerService` | Sandbox execution | Spawn containers, run agent loop, capture output |
| `EvaluationService` | Aspect evaluation | Run reproducibility checks across 15 dimensions |
| `EventDispatcher` | Central event hub | Persist events, update job status, handle transitions |
| `JobService` | Job lifecycle | CRUD operations, user isolation, progress tracking |
| `CacheService` | Multi-layer caching | Check/store cache at 3 layers (paper/code/eval) |
| `AuthService` | User authentication | Login, registration, password hashing |
| `LLMService` | LLM abstraction | Multi-provider support (Anthropic, Ollama, etc.) |

---

## Real-Time Updates

### Polling Architecture

Frontend uses **polling** (not SSE) for reliability:

**How Polling Works:**
```
User uploads PDF
  ↓
POST /api/upload → creates job, starts background thread
  ↓
Returns job_id immediately to frontend
  ↓
Frontend polls every 200ms:
  GET /api/job/<id>/full
    → Returns: {status, progress, current_stage, events: [...]}
  ↓
Frontend updates UI:
  - Progress bar (0.0 → 1.0)
  - Section visibility (show when data ready)
  - Event log (append new events)
```

**Endpoint: `/api/job/<id>/full`**
```json
{
  "id": "uuid",
  "status": "processing",
  "progress": 0.45,
  "current_stage": "code_execution",
  "events": [
    {"step": "stage_1_starting", "progress": 0.05, "timestamp": "..."},
    {"step": "pdf_extracted", "progress": 0.25, "timestamp": "..."},
    {"step": "stage_1_complete", "progress": 0.33, "timestamp": "..."},
    ...
  ],
  "paper_analysis": {title, abstract, citations, ...},
  "execution_details": {commands_run, stdout, actual_results, ...},
  "aspect_evaluations": [{aspect_id, name, status, evidence, ...}, ...]
}
```

### EventDispatcher Role

`EventDispatcher` is the **central event hub**:
1. **Receives events** from all stages (via `emit()` method)
2. **Persists to database** - writes to Event table (except chat events)
3. **Updates Job record** - sets status, progress, current_stage on stage transitions
4. **Logs everything** - comprehensive logging for debugging

**Stage Transition Events (trigger job status updates):**
- `stage_1_starting` → current_stage = "paper_analysis"
- `stage_1_complete` → current_stage = "code_execution"
- `stage_2_starting` → current_stage = "code_execution"
- `stage_2_complete` → current_stage = "evaluation"
- `stage_3_starting` → current_stage = "evaluation"
- `stage_3_complete` → current_stage = "evaluation"
- `complete` → status = "completed", current_stage = "completed"

**Progress Flow:**
```
PipelineOrchestrator emits event with progress value
  ↓
EventDispatcher.emit(JobEvent(..., progress=0.45))
  ↓
EventDispatcher logs progress: "*** EVENT INCLUDES PROGRESS: progress=0.45 ***"
  ↓
EventDispatcher._persist_event() → writes to Event table
  ↓
EventDispatcher._handle_stage_transition() → updates Job.progress in database
```

---

## Data Flow

### Complete Workflow

```
1. USER UPLOADS PDF
   POST /api/upload
   ↓ Validates file, creates Job record (progress=0.0)
   ↓ Returns job_id to frontend

2. BACKGROUND THREAD SPAWNED
   analyze_paper_background() runs in thread pool
   ↓ Calls PipelineOrchestrator.run_analysis()

3. STAGE 1: PAPER ANALYSIS
   emit_event("stage_1_starting", progress=0.05)
     ↓ EventDispatcher persists, updates Job
   extract_and_analyze_pdf()
     ↓ Check CachePaperAnalysis by PDF hash (cache hit = 1-2s)
     ↓ If miss: Call Claude to extract metadata
   store PaperAnalysis record
   emit_event("stage_1_complete", progress=0.33)
     ↓ EventDispatcher updates Job.current_stage="code_execution"

4. STAGE 2: CODE EXECUTION
   emit_event("stage_2_starting", progress=0.35)
   For each GitHub artifact:
     spawn_agent_container(repo_url)
       ↓ Clone repo → discover files → agent loop (max 15 iterations)
       ↓ Agent asks Claude: "What should I do?"
       ↓ Execute action (read_file, run_command, done)
       ↓ Collect output and results
   Check CacheCodeExecution by repo hash
   store ExecutionDetails record
   emit_event("stage_2_complete", progress=0.66)
     ↓ EventDispatcher updates Job.current_stage="evaluation"

5. STAGE 3: EVALUATION
   emit_event("stage_3_starting", progress=0.75)
   Call Claude with all context:
     - Paper claims (title, abstract, methodology)
     - Code execution (commands, output, results)
     - Artifacts discovered
   Claude evaluates 15 reproducibility aspects
   Check CacheEvaluation by (paper_hash, code_hash)
   For each aspect:
     store AspectEvaluation record
   emit_event("stage_3_complete", progress=0.99)

6. PIPELINE COMPLETION
   emit_event("complete")
     ↓ EventDispatcher updates Job.status="completed", progress=1.0
   Return to frontend (polling catches update)

7. FRONTEND POLLING
   Every 200ms: GET /api/job/<id>/full
   ↓ Receives job state + all events
   ↓ Updates progress bar, appends events, shows results
```

### Repository Persistence

Data persists via repositories at each stage:

```
Stage 1:
  PaperAnalysisRepository.create(job_id, ...)
    ↓ Peewee: INSERT INTO paper_analysis
    
Stage 2:
  ExecutionDetailsRepository.create(job_id, ...)
    ↓ Peewee: INSERT INTO execution_details
    
Stage 3:
  AspectEvaluationRepository.create_batch(job_id, evaluations)
    ↓ Peewee: INSERT INTO aspect_evaluations (15+ rows)
    
Events:
  EventDispatcher._persist_event()
    ↓ Peewee: INSERT INTO events
    ↓ Tracks every state transition, progress update, error
```

---

## Execution Model

### Agent Container Sandbox

Each code execution spawns an isolated Docker container with:
- **Memory:** 2GB limit
- **CPU:** 2 cores max
- **Timeout:** 300 seconds per command
- **Network:** Can reach Flask backend on Docker network
- **Filesystem:** `/workspace/repo` (cloned repository only)
- **User:** Non-root for safety

### Agent Loop

Agent communicates with Flask backend via HTTP:

```
1. Clone repository to /workspace/repo
2. Discover files (requirements.txt, setup.py, tests, etc.)
3. For iteration 1 to 15:
   - POST /api/agent/think
     Request: {job_id, repo_state, history}
     Response: {action, params}
   - Execute action:
     * read_file: Read source code, config files
     * run_command: Execute bash command
     * check_success: Verify reproducibility metrics
     * done: Mark complete
   - POST /api/agent/log (emit events)
   - On error: Retry same action or move to next
4. Exit and cleanup container
```

**Agent never accesses:**
- Backend code or database directly
- Host filesystem (except via `/workspace`)
- External APIs (uses Flask backend instead)
- Anthropic API key (backend proxies requests)

---

## Networking

All containers on shared Docker network (workspace_traefik):
- **Flask app:** `http://paper-reproducibility:5000`
- **Agent containers:** Ephemeral, spawn on demand
- **DNS:** Docker's internal DNS (auto-discovery by hostname)

---

## Security

### Isolation
- ✅ **Docker containers** - filesystem isolation per job
- ✅ **Resource limits** - memory, CPU, timeout prevent DoS
- ✅ **Non-root user** - containers run as unprivileged user
- ✅ **No host access** - only /var/run/docker.sock for container control

### Credentials
- ✅ **API keys in environment** - never in code or containers
- ✅ **Agent proxy** - agent calls Flask backend, which proxies LLM requests
- ✅ **User isolation** - jobs filtered by user_id in database queries

### Input Validation
- ✅ **PDF size limit** - 100MB max (prevent memory exhaustion)
- ✅ **Path traversal prevention** - validate file paths with `.resolve().is_relative_to()`
- ✅ **Command timeout** - 300 seconds per command (prevent infinite loops)
- ✅ **Output truncation** - limit output size in events to prevent UI issues

---

## Performance

### Caching Layers

Three-layer caching provides 100-300x speedup for repeated analyses:

1. **Paper Analysis Cache** (by PDF hash)
   - Stores: Title, abstract, citations, methodology
   - Benefit: Skip Claude parsing for duplicate PDFs

2. **Code Execution Cache** (by repo hash)
   - Stores: Commands, output, results, dependencies
   - Benefit: Skip Docker agent execution for known repos

3. **Evaluation Cache** (by paper+code hash)
   - Stores: All 15 aspect evaluations with evidence
   - Benefit: Skip evaluation Claude call for known combinations

### Timing

| Scenario | Time | Bottleneck |
|----------|------|-----------|
| No cache (new paper + new repo) | 3-5 min | Repository size, Claude latency |
| Cache hits (seen paper + seen repo) | 1-2 sec | Database lookups |
| Mixed (new paper + seen repo) | 2-3 min | Paper parsing + eval |
| Paper parsing only | 5-10 sec | Claude latency |

**Cost Reduction:** Using Haiku instead of Opus reduces LLM costs by 80% while maintaining 90%+ accuracy.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML/CSS/JavaScript | Web UI |
| **Component Lib** | DaisyUI + Tailwind | Professional UI components |
| **Real-Time** | Polling via fetch API | Live updates every 200ms |
| **Backend** | Flask | Web framework |
| **ORM** | Peewee | Type-safe database access |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Data persistence |
| **Auth** | Werkzeug PBKDF2 | Secure password hashing |
| **Agent Exec** | Python subprocess | Command execution in agent container |
| **Sandbox** | Docker + Docker SDK | Container isolation and management |
| **LLM** | Claude (Anthropic) + Ollama abstraction | AI reasoning and evaluation |
| **Testing** | pytest + fixtures | Unit and integration tests |
