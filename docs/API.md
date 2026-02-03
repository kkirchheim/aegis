# API Reference

Complete HTTP API documentation for the Paper Reproducibility Checker.

## Base URL

```
http://localhost:5000
```

## Content Types

- Request: `multipart/form-data` (uploads) or `application/json`
- Response: `application/json` or `text/event-stream` (SSE)

---

## Public Endpoints

### Upload PDF

**POST /upload**

Upload a scientific paper for analysis.

```bash
curl -X POST -F "pdf=@paper.pdf" http://localhost:5000/upload
```

**Response (202):**
```json
{
  "job_id": "abc123...",
  "message": "Paper uploaded successfully..."
}
```

**Constraints:**
- Max 100MB
- PDF format only

---

### Stream Progress

**GET /events/{job_id}**

Real-time progress via Server-Sent Events (SSE).

```javascript
const es = new EventSource(`/events/${jobId}`);
es.onmessage = (e) => console.log(JSON.parse(e.data));
```

**Event Types:**
- `starting` - Job initialized
- `extracting_pdf` - Reading PDF
- `parsing_paper` - Claude analysis
- `analyzing_artifact` - Executing code
- `complete` - Success (includes report)
- `error` - Failed

---

### Get Job Status

**GET /job/{job_id}**

Fetch complete job data (paper analysis, execution, evaluation).

```bash
curl http://localhost:5000/job/abc123
```

**Response:**
```json
{
  "id": "abc123",
  "status": "completed",
  "pdf_filename": "paper.pdf",
  "report": {
    "status": "success",
    "reproducibility_score": 0.87,
    "aspect_evaluations": [...]
  },
  "events": [...],
  "artifacts": [...]
}
```

---

### List Jobs

**GET /jobs**

List all analysis jobs.

```bash
curl http://localhost:5000/jobs
```

**Response:**
```json
[
  {
    "id": "abc123",
    "status": "completed",
    "pdf_filename": "paper.pdf",
    "created_at": "2026-02-03T...",
    "completed_at": "2026-02-03T..."
  },
  ...
]
```

---

## Internal Agent Endpoints

Used by Docker agent (not for external clients).

### Ask Claude What to Do

**POST /api/agent/think**

Agent asks Claude for next action.

```json
{
  "job_id": "abc123",
  "repo_state": {
    "repo_url": "https://github.com/...",
    "discovered_files": ["README.md", "requirements.txt", ...],
    "last_output": "...",
    "errors": [],
    "iteration": 5
  }
}
```

**Response:**
```json
{
  "action": "run_command",
  "target": "python script.py",
  "reasoning": "Execute the main script to verify reproducibility"
}
```

---

### Log Progress

**POST /api/agent/log**

Agent logs progress (emitted to SSE stream).

```json
{
  "job_id": "abc123",
  "message": "Running iris_classification.py"
}
```

---

### Submit Execution Details

**POST /api/agent/execution**

Agent submits collected execution details for evaluation.

```json
{
  "job_id": "abc123",
  "commands_run": "pip install requirements.txt\npython script.py",
  "stdout_combined": "Output here...",
  "actual_results": {"accuracy": 0.93},
  "dependencies_used": "numpy==1.21.0\nscikit-learn==1.0.1",
  "errors_summary": "None"
}
```

---

### Report Completion

**POST /api/agent/complete**

Agent signals completion (success or failure).

```json
{
  "job_id": "abc123",
  "success": true,
  "message": "Script executed successfully",
  "accuracy": 0.93,
  "reproducibility_aspects": {
    "aspects": [...]
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "File must be a PDF"
}
```

### 404 Not Found
```json
{
  "error": "Job not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error message"
}
```

---

## Rate Limiting

Currently no rate limits. Will be added in production deployment.

---

## Database Endpoints

### Get Full Job Data

**GET /api/job/{job_id}/full**

Returns complete job data including events, artifacts, evaluations.

Used by detail page to fetch all information.

**Response includes:**
- `events` - All SSE events (timestamps, steps)
- `artifacts` - Code artifacts found
- `report` - Analysis report
- `aspect_evaluations` - Reproducibility scores

---

### Delete Job

**DELETE /job/{job_id}**

Delete a job and all related data.

```bash
curl -X DELETE http://localhost:5000/job/abc123
```

**Response:**
```json
{
  "ok": true,
  "message": "Job deleted"
}
```

---

## Example Workflow

```bash
# 1. Upload paper
JOB_ID=$(curl -s -X POST -F "pdf=@paper.pdf" \
  http://localhost:5000/upload | jq -r '.job_id')

# 2. Stream events in real-time
curl -N http://localhost:5000/events/$JOB_ID &

# 3. Wait for completion, then fetch results
sleep 5
curl http://localhost:5000/job/$JOB_ID | jq '.report'
```
