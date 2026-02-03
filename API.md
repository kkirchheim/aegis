# API Reference - Paper Reproducibility Checker

## Overview

This document describes all HTTP endpoints for the Paper Reproducibility Checker API.

## Base URL

```
http://localhost:5000
```

Or in Docker:
```
http://host.docker.internal:5000
```

## Authentication

Currently no authentication required for MVP. Authentication will be added in Phase 4.

## Content Types

- Request: `multipart/form-data` (file uploads) or `application/json`
- Response: `application/json` or `text/event-stream` (for SSE)

## Endpoints

### 1. Frontend Pages

#### GET /
Serves the main web interface.

**Response:** HTML page

---

### 2. PDF Upload

#### POST /upload

Upload a scientific paper for reproducibility analysis.

**Request:**
```
Content-Type: multipart/form-data

- pdf: <binary PDF file>
```

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Paper uploaded successfully. Analysis starting..."
}
```

**Error Response (400):**
```json
{
  "error": "File must be a PDF"
}
```

**Status Codes:**
- `202` - Job created successfully
- `400` - Bad request (no file, wrong format, too large)
- `500` - Server error

**Constraints:**
- Max file size: 100MB
- File must be `.pdf`
- Non-empty file required

**Example:**
```bash
curl -X POST \
  -F "pdf=@paper.pdf" \
  http://localhost:5000/upload
```

---

### 3. Real-Time Progress Stream

#### GET /events/<job_id>

Stream real-time analysis progress via Server-Sent Events (SSE).

**Parameters:**
- `job_id` (path) - Job ID from upload response

**Response:** `text/event-stream` (persistent HTTP connection)

**Event Format:**
```
data: {
  "step": "parsing_pdf",
  "message": "Extracting text from PDF...",
  "progress": 10,
  "timestamp": "2026-02-03T12:30:45.123Z"
}

```

**Event Types:**

| Step | Message | Progress | Notes |
|------|---------|----------|-------|
| `starting` | Analysis starting... | 0 | Job initialized |
| `extracting_pdf` | Extracting text from PDF... | 10 | Reading PDF |
| `pdf_extracted` | Extracted X characters... | 20 | Complete |
| `parsing_paper` | Analyzing paper with Claude... | 25 | Calling LLM |
| `paper_parsed` | Found X code artifacts | 40 | Parsing done |
| `analyzing_artifact` | Analyzing: <url> | 45-90 | Per-artifact analysis |
| `complete` | Analysis complete | 100 | Success (includes report) |
| `error` | Error: <message> | - | Failed |

**Example (JavaScript):**
```javascript
const eventSource = new EventSource(`/events/${jobId}`);

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`[${data.step}] ${data.message}`);
};

eventSource.onerror = () => {
    console.error("Connection lost");
};
```

**Example (cURL):**
```bash
curl -N http://localhost:5000/events/550e8400-e29b-41d4-a716-446655440000
```

---

### 4. Get Job Status

#### GET /job/<job_id>

Get current status and results of a job.

**Parameters:**
- `job_id` (path) - Job ID

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2026-02-03T12:00:00.000Z",
  "completed_at": "2026-02-03T12:15:30.000Z",
  "report": {
    "code_found": true,
    "artifacts": [
      {
        "url": "https://github.com/user/repo",
        "type": "github_repo",
        "description": "Main implementation code"
      }
    ],
    "reproducibility_aspects": {
      "hyperparameters_documented": true,
      "implementation_details": "sufficient",
      "dataset_description": "MNIST dataset available at keras.io",
      "environment_requirements": "Python 3.8+, TensorFlow 2.0+"
    },
    "summary": "Paper has good reproducibility documentation..."
  }
}
```

**Response (404):**
```json
{
  "error": "Job not found"
}
```

**Status Codes:**
- `200` - Job found
- `404` - Job not found

**Job Status Values:**
- `pending` - Queued, not started
- `processing` - Currently analyzing
- `completed` - Finished successfully
- `error` - Failed with error

---

### 5. List All Jobs

#### GET /jobs

List all analysis jobs with summary info.

**Response (200):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "pdf_filename": "paper.pdf",
    "created_at": "2026-02-03T12:00:00.000Z",
    "completed_at": "2026-02-03T12:15:30.000Z"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440111",
    "status": "processing",
    "pdf_filename": "another_paper.pdf",
    "created_at": "2026-02-03T13:00:00.000Z",
    "completed_at": null
  }
]
```

**Query Parameters:**
- `limit` (optional) - Max results (default: 50)
- `status` (optional) - Filter by status (pending, processing, completed, error)

**Response:**
- Array of job objects
- Sorted by creation date (newest first)
- Max 50 results

---

## Agent API (Internal)

These endpoints are called by the LLM agent running inside Docker containers.

### 6. Agent: Ask Claude

#### POST /api/agent/think

Agent asks Claude what to do next.

**Request:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "repo_state": {
    "stage": "initial",
    "cwd": "/workspace/repo",
    "files": ["README.md", "setup.py", "requirements.txt", "src/"],
    "last_output": {
      "returncode": 0,
      "stdout": "Successfully installed dependencies",
      "stderr": ""
    },
    "last_command": "pip install -r requirements.txt",
    "completed_steps": ["git clone", "pip install -r requirements.txt"],
    "errors": []
  }
}
```

**Response (200):**
```json
{
  "action": "run_command",
  "target": "python train.py",
  "reasoning": "README says to run python train.py to train the model",
  "check_for": "Training complete"
}
```

**Action Types:**
- `read_file` - Read a file in repo
- `run_command` - Execute shell command
- `check_success` - Confirm execution succeeded
- `done` - Finished, exit loop

**Status Codes:**
- `200` - Success (Claude returned action)
- `400` - Bad request (missing job_id)
- `500` - Server error (Claude API failed)

---

### 7. Agent: Log Progress

#### POST /api/agent/log

Agent reports progress back to backend.

**Request:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Installing dependencies..."
}
```

**Response (200):**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200` - Log message received
- `400` - Bad request (missing job_id)

**Message Examples:**
- "Cloning repository..."
- "✓ Dependencies installed successfully"
- "✗ Installation failed: package not found"
- "Found README.md, analyzing instructions"
- "Executing: python train.py"

---

## Error Responses

All errors follow this format:

```json
{
  "error": "Human-readable error message"
}
```

**Common Errors:**

| Status | Error | Cause |
|--------|-------|-------|
| `400` | "No PDF file provided" | Missing file in upload |
| `400` | "File too large (max 100MB)" | PDF exceeds size limit |
| `400` | "File must be a PDF" | Wrong file format |
| `400` | "job_id required" | Missing required parameter |
| `404` | "Job not found" | Invalid job_id |
| `500` | "Claude API error: ..." | LLM API failure |
| `500` | "Failed to extract PDF: ..." | PDF parsing error |

---

## Rate Limiting (Phase 4)

Rate limiting will be implemented in Phase 4. Currently no limits.

**Planned limits:**
- 10 uploads per minute per IP
- 5 concurrent jobs
- 1 job per minute per IP

---

## Webhooks (Phase 4)

Future version will support webhooks for job completion:

```
POST https://your-domain.com/webhook
Content-Type: application/json

{
  "event": "job.completed",
  "job_id": "...",
  "status": "completed",
  "report": {...}
}
```

---

## Examples

### Complete Upload → Monitor → Get Report Flow

```bash
# 1. Upload PDF
RESPONSE=$(curl -X POST \
  -F "pdf=@paper.pdf" \
  http://localhost:5000/upload)

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 2. Monitor progress (in separate terminal)
curl -N http://localhost:5000/events/$JOB_ID

# 3. Get final report (after completion)
curl http://localhost:5000/job/$JOB_ID | jq '.report'
```

### JavaScript Example

```javascript
// Upload
const formData = new FormData();
formData.append('pdf', fileInput.files[0]);

const uploadRes = await fetch('/upload', {
  method: 'POST',
  body: formData
});

const { job_id } = await uploadRes.json();

// Monitor
const es = new EventSource(`/events/${job_id}`);
es.onmessage = (e) => {
  const { step, message, progress } = JSON.parse(e.data);
  console.log(`${progress}% - ${message}`);
};

// Get report
const jobRes = await fetch(`/job/${job_id}`);
const { report } = await jobRes.json();
console.log(report);
```

---

## Performance Tips

1. **Don't poll** - Use SSE for progress updates
2. **Cache job IDs** - Store job_id for later retrieval
3. **Batch uploads** - Multiple jobs can run in parallel
4. **Stream monitoring** - Don't wait for completion before streaming

---

## Changelog

### Phase 1 (Current)
- ✅ POST /upload
- ✅ GET /events/<job_id>
- ✅ GET /job/<job_id>
- ✅ GET /jobs
- ✅ POST /api/agent/think
- ✅ POST /api/agent/log

### Phase 2
- [ ] Proper authentication
- [ ] Rate limiting
- [ ] Pagination for /jobs

### Phase 3
- [ ] WebSocket support (optional)
- [ ] Webhooks
- [ ] Advanced filtering
- [ ] Export reports (PDF, JSON)

---

**Last Updated:** February 3, 2026  
**Version:** 1.0  
**Status:** MVP Phase 1
