# System Architecture

High-level design and data flow of the Paper Reproducibility Checker.

## Three-Stage Pipeline

```
┌─────────────────────────────────────┐
│ STAGE 1: PAPER ANALYSIS             │
├─────────────────────────────────────┤
│ • Extract PDF text                  │
│ • Claude parses methodology          │
│ • Identify code artifacts            │
│ → Store in paper_analysis table     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ STAGE 2: CODE EXECUTION             │
├─────────────────────────────────────┤
│ • Clone GitHub repository            │
│ • Discover files (tests, config)    │
│ • Execute main script in sandbox    │
│ • Capture all output & results      │
│ → Store in execution_details table  │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ STAGE 3: MULTI-SOURCE EVALUATION    │
├─────────────────────────────────────┤
│ • Claude receives all three sources  │
│ • Evaluates 15 reproducibility      │
│   aspects comparing claims vs exec   │
│ → Store in aspect_evaluations table │
└──────────────┬──────────────────────┘
               ↓
         Report Display
```

## System Components

### Frontend
- **HTML:** Upload form, progress log, job history
- **CSS:** Tailwind + DaisyUI for professional UI
- **JavaScript:** Real-time updates via SSE, interactions

### Backend (Flask)
- **PDF Handler:** Extract text, store files
- **Claude Interface:** Send to API, parse responses
- **Agent Coordinator:** Spawn Docker containers, manage jobs
- **Database:** SQLite with 6 tables
- **SSE Broadcaster:** Stream events to frontend

### Agent (Docker Container)
- **Repository Cloning:** Git clone + fetch
- **File Discovery:** Find tests, config, licenses
- **Code Execution:** Run scripts in sandbox
- **Backend Communication:** HTTP POST to ask Claude + log results

### External Services
- **Anthropic API:** Claude LLM for parsing, evaluation, reasoning
- **GitHub:** Source repositories

## Database Schema

### Tables

**jobs**
- id (UUID, PK)
- status (pending, processing, completed, failed)
- pdf_path, pdf_filename
- report (JSON with scores & evaluation results)
- created_at, completed_at

**artifacts**
- id (auto-inc)
- job_id (FK)
- url (GitHub repo, dataset URL, etc.)
- artifact_type (github, dataset, docker, etc.)
- description

**events**
- id (auto-inc)
- job_id (FK)
- timestamp
- step (starting, extracting_pdf, parsing_paper, etc.)
- message
- severity (info, warning, error)

**paper_analysis**
- id (auto-inc)
- job_id (unique FK)
- pdf_hash (MD5 of full PDF for caching)
- title (extracted paper title)
- abstract (extracted paper abstract)
- citations (JSON array of citations: {authors, year, title, url})
- extracted_text (first 50k chars of PDF)
- claimed_results (JSON)
- methodology, dependencies, dataset_description

**execution_details**
- id (auto-inc)
- job_id (unique FK)
- commands_run (all bash commands executed)
- stdout_combined (full output log)
- actual_results (parsed metrics: accuracy, loss, etc.)
- dependencies_used (pip list output)
- errors_summary (last 5 errors)

**aspect_evaluations**
- id (auto-inc)
- job_id (FK)
- aspect_id (dependencies_pinned, results_reproducible, etc.)
- name, status (pass, partial, fail)
- evidence (finding from all sources)
- paper_supports, code_supports (booleans)
- conclusion

## 15 Reproducibility Aspects

### Tier 1: CRITICAL
1. Dependencies Pinned - Exact versions (==)?
2. Results Reproducible - Execution matches paper claims?
3. Hyperparameters Documented - Values documented AND correct?
4. Dataset Available - Data public/easy to obtain?
5. Environment Documented - Python version, OS, etc.?

### Tier 2: HIGH VALUE
6. Test Suite Present - Tests included?
7. Config File Present - Hyperparameters externalized?
8. Documentation Quality - README, comments, docstrings?
9. Randomness Controlled - Seeds set?

### Tier 3: NICE-TO-HAVE
10. License Specified
11. Continuous Integration
12. Data Versioning
13. Computational Requirements
14. Output Format Documented
15. Python Version Compatibility

## Data Flow

### Workflow: Upload → Analyze → Report

```
1. USER UPLOADS PDF
   ↓
2. Backend validates file, creates job record
   ↓
3. Background thread starts analysis
   ↓
4. Extract PDF text
   ↓
5. Call Claude to parse paper
   → Identifies code artifacts
   → Extracts methodology, claims
   ↓
6. For each GitHub artifact:
   a. Spawn Docker container
   b. Agent clones repo
   c. Agent loop (max 15 iterations):
      - Ask Claude: "What should I do?"
      - Execute action (read file, run command)
      - Report results back
   d. Collect execution output & results
   ↓
7. Trigger Stage 3: Multi-source Evaluation
   Claude compares:
   - What paper claimed
   - What code actually does
   - What execution achieved
   ↓
8. Generate report (15 aspects scored)
   ↓
9. Frontend displays checklist with evidence
```

### Real-Time Events (SSE)

Each stage emits events that frontend receives:

```
starting (0%) → extracting_pdf (10%) → pdf_extracted (20%)
  → parsing_paper (25%) → paper_parsed (40%)
  → analyzing_artifact (50-90%) → evaluating_aspects (95%)
  → complete (100%)
```

Frontend shows live progress bar + log entries.

## Execution Model

### Agent Container Sandbox

Each job spawns isolated Docker container with:
- **Memory limit:** 2GB RAM
- **CPU limit:** 2 cores
- **Timeout:** 300 seconds per command
- **Network:** Isolated (can reach backend on shared Docker network)
- **Filesystem:** /workspace/repo (cloned repository)
- **Security:** Non-root user, no host access

### Agent Loop

Agent runs inside container and communicates only via HTTP:

```
1. Clone repo from URL
2. List files (discover_files)
3. For iteration 1 to 15:
   - POST to /api/agent/think
     (sends: job_id + repo_state)
   - Claude returns JSON action
   - Execute action:
     * read_file: Read and store content
     * run_command: Execute bash command
     * check_success: Verify reproducibility
     * done: Finished
   - POST to /api/agent/log (emit events)
4. Exit (normal, error, or max iterations)
```

No direct access to:
- Backend code or database
- Host filesystem
- Other containers
- External APIs (except via backend)

## Networking

All containers on `workspace_traefik` network:
- Flask app: `http://paper-reproducibility:5000`
- Agent containers: spawn dynamically, isolated
- DNS: Docker's internal DNS resolves container names

## Security

### Isolation
- ✅ Docker containers (filesystem isolation)
- ✅ Resource limits (memory, CPU, timeout)
- ✅ Non-root user in containers
- ✅ No host mount (except /var/run/docker.sock for meta-control)

### Credentials
- ✅ ANTHROPIC_API_KEY in environment only
- ✅ Never passed to agent
- ✅ Agent calls backend API instead

### Input Validation
- ✅ PDF size limit (100MB)
- ✅ Path traversal prevention
- ✅ Command timeout (300s)
- ✅ Output truncation (prevent context explosion)

## Caching System

Three-layer caching reduces redundant API calls and agent execution:

### Layer 1: Paper Analysis Cache
- **Key:** MD5 hash of PDF text
- **Stores:** Title, abstract, citations, methodology, dependencies
- **Benefit:** Skip Claude parsing for duplicate PDFs
- **Table:** `cache_paper_analysis`

### Layer 2: Code Execution Cache
- **Key:** Repository URL + code hash
- **Stores:** Commands run, output, execution results, dependencies
- **Benefit:** Skip Docker agent execution for known repos
- **Table:** `cache_code_execution`

### Layer 3: Evaluation Cache
- **Key:** Paper hash + code hash
- **Stores:** All 15 aspect evaluations with evidence
- **Benefit:** Skip evaluation Claude call for known combinations
- **Table:** `cache_evaluation`

**Cache Miss Scenario:** New PDF + unknown repo = full 3-5 minute pipeline
**Cache Hit Scenario:** Seen PDF + seen repo = ~1-2 seconds (cached results)

## Agent Context Management

The agent sees full command + output history to avoid loops:

```
Iteration 1: read_file(README.md) → [output]
Iteration 2: read_file(requirements.txt) → [output]
Iteration 3: [Claude sees full history] → moves to pip install
```

**Configuration:**
- `AGENT_CONTEXT_LIMIT` environment variable (default: 10000 chars)
- Controls max output shown to agent per iteration
- Increase if agent loops, decrease if context too large

## Performance

- **Paper extraction (no cache):** 5-10 seconds
- **Paper extraction (cache hit):** <1 second
- **Code execution (no cache):** 2-5 minutes (repo-dependent)
- **Code execution (cache hit):** <1 second
- **Evaluation (no cache):** 10-15 seconds
- **Evaluation (cache hit):** <1 second
- **Total (worst case):** ~3-5 minutes per paper
- **Total (best case with cache):** ~1-2 seconds

Bottleneck: Depends on repo size and agent execution complexity.
Caching provides 100-300x speedup for repeated analyses.

## Deployment Targets

### Local Development
- Single Flask process (debug mode)
- SQLite in-container
- Agent containers on same host

### Production
- Gunicorn + multiple workers
- PostgreSQL (replace SQLite)
- Nginx reverse proxy + HTTPS
- Monitoring + logging aggregation
- Multi-node agent execution (optional)

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production setup.

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | HTML/CSS/JS + Tailwind | Web UI |
| Frontend UI | DaisyUI | Component library |
| Real-time | Server-Sent Events (SSE) | Live updates |
| Backend | Flask | Web framework |
| Database | SQLite (dev) / PostgreSQL (prod) | Data storage |
| Agent Runtime | Python subprocess | Command execution |
| Isolation | Docker | Container sandboxing |
| LLM | Claude (Anthropic) | AI reasoning |
