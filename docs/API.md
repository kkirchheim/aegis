# API Reference

Complete HTTP API documentation for the Paper Reproducibility Checker.

## Table of Contents

- [Base URL](#base-url)
- [Content Types](#content-types)
- [Public Endpoints](#public-endpoints)
- [Polling Endpoint](#polling-endpoint)
- [List Jobs](#list-jobs)
- [Chat Endpoints](#chat-endpoints)
- [Internal Agent Endpoints](#internal-agent-endpoints)
- [Database Endpoints](#database-endpoints)
- [Error Responses](#error-responses)
- [Rate Limiting](#rate-limiting)
- [Example Workflow](#example-workflow)

---

## Base URL

```
http://localhost:5000
```

## Content Types

- Request: `multipart/form-data` (uploads) or `application/json`
- Response: `application/json`

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

### Get Job Status

**GET /job/{job_id}**

Fetch job status (brief overview).

```bash
curl http://localhost:5000/job/abc123
```

**Response:**
```json
{
  "id": "abc123",
  "status": "completed",
  "created_at": "2026-02-03T...",
  "completed_at": "2026-02-03T...",
  "report": {
    "status": "success",
    "reproducibility_score": 0.87,
    "aspect_evaluations": [...]
  }
}
```

---

### List Jobs

**GET /jobs**

List all analysis jobs for the current user.

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

## Polling Endpoint

### Get Full Job Data

**GET /api/job/{job_id}/full**

Fetch complete job data including all details, events, and progress.

Used by the frontend to poll for updates. Call this endpoint repeatedly to track job progress.

```bash
curl http://localhost:5000/api/job/abc123/full
```

**Response:**
```json
{
  "id": "abc123",
  "status": "processing",
  "progress": 0.65,
  "current_stage": "analyzing_artifact",
  "pdf_filename": "paper.pdf",
  "created_at": "2026-02-03T10:00:00Z",
  "completed_at": null,
  "report": {
    "status": "success",
    "reproducibility_score": 0.87,
    "aspect_evaluations": [...]
  },
  "error_message": null,
  "events": [
    {
      "step": "starting",
      "message": "Job initialized",
      "timestamp": "2026-02-03T10:00:01Z"
    },
    {
      "step": "extracting_pdf",
      "message": "Reading PDF",
      "timestamp": "2026-02-03T10:00:05Z"
    },
    {
      "step": "parsing_paper",
      "message": "Analyzing with Claude",
      "timestamp": "2026-02-03T10:01:00Z"
    }
  ],
  "artifacts": [
    {
      "id": "art1",
      "job_id": "abc123",
      "path": "/code/script.py",
      "type": "code",
      "content": "..."
    }
  ],
  "paper_analysis": {
    "title": "Improving Image Classification with...",
    "abstract": "This paper proposes...",
    "citations": [
      {
        "authors": ["Smith, J.", "Doe, A."],
        "year": 2023,
        "title": "Deep Learning Advances",
        "url": "https://arxiv.org/..."
      }
    ]
  }
}
```

**Response Fields:**
- `progress` - Float 0.0-1.0 indicating job progress
- `current_stage` - Current pipeline stage (starting, extracting_pdf, parsing_paper, analyzing_artifact, complete)
- `events` - Array of all events emitted during job execution
- `artifacts` - Code/output artifacts extracted from the paper
- `paper_analysis` - Extracted metadata (title, abstract, citations)

**Frontend Usage:**
Poll this endpoint every 1-2 seconds while status is `processing` or `pending`:

```javascript
async function pollJob(jobId) {
  while (true) {
    const response = await fetch(`/api/job/${jobId}/full`);
    const job = await response.json();
    
    console.log(`Progress: ${job.progress * 100}%`);
    console.log(`Stage: ${job.current_stage}`);
    
    if (['completed', 'failed', 'error'].includes(job.status)) {
      break;
    }
    
    await new Promise(r => setTimeout(r, 1000)); // wait 1 second
  }
}
```

---

## Chat Endpoints

### Send Message

**POST /api/job/{job_id}/chat**

Send a message about the paper analysis and get a streaming response.

```bash
curl -X POST http://localhost:5000/api/job/abc123/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why did the code fail?"}'
```

**Request:**
```json
{
  "message": "Why did the code fail?"
}
```

**Response (202):**
```json
{
  "ok": true
}
```

**Streaming Response:**
The response is streamed via events in the job's event stream. Listen for events with `step: "chat_response"`:

```json
{
  "step": "chat_response",
  "content": "The code failed because..."
}
```

---

### Get Chat History

**GET /api/job/{job_id}/chat/history**

Retrieve the conversation history for a job.

```bash
curl http://localhost:5000/api/job/abc123/chat/history
```

**Response:**
```json
[
  {
    "role": "user",
    "content": "Why did the code fail?",
    "created_at": "2026-02-03T10:30:00Z"
  },
  {
    "role": "assistant",
    "content": "The code failed because of a missing dependency...",
    "created_at": "2026-02-03T10:30:05Z"
  }
]
```

---

### Clear Chat History

**DELETE /api/job/{job_id}/chat/history**

Delete all chat messages for a job.

```bash
curl -X DELETE http://localhost:5000/api/job/abc123/chat/history
```

**Response:**
```json
{
  "ok": true,
  "message": "Chat history cleared"
}
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
    "combined_output": "...",
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

Agent logs progress.

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
  "message": "Script executed successfully"
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

### 403 Forbidden
```json
{
  "error": "Access denied"
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

### Cache Management

#### Get Cache Statistics

**GET /api/cache/stats**

Returns current cache usage.

**Response:**
```json
{
  "paper_analysis": 5,
  "code_execution": 12,
  "evaluation": 8,
  "total": 25
}
```

#### Clear All Cache

**DELETE /api/cache/clear**

Clears all cached data (paper analysis, code execution, evaluations) and deletes uploaded PDFs.

```bash
curl -X DELETE http://localhost:5000/api/cache/clear
```

**Response:**
```json
{
  "ok": true,
  "message": "Cache cleared - deleted 5 PDF files"
}
```

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

### Polling-Based Progress Tracking

```bash
#!/bin/bash

# 1. Upload paper
JOB_ID=$(curl -s -X POST -F "pdf=@paper.pdf" \
  http://localhost:5000/upload | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 2. Poll for progress until completion
while true; do
  RESPONSE=$(curl -s http://localhost:5000/api/job/$JOB_ID/full)
  
  STATUS=$(echo "$RESPONSE" | jq -r '.status')
  PROGRESS=$(echo "$RESPONSE" | jq -r '.progress')
  STAGE=$(echo "$RESPONSE" | jq -r '.current_stage')
  
  echo "Status: $STATUS | Progress: ${PROGRESS}% | Stage: $STAGE"
  
  if [[ "$STATUS" == "completed" ]] || [[ "$STATUS" == "failed" ]]; then
    break
  fi
  
  sleep 1
done

# 3. Fetch final results
curl -s http://localhost:5000/api/job/$JOB_ID/full | jq '.report'
```

### JavaScript Polling Example

```javascript
async function analyzeAndWait(pdfFile) {
  // Upload
  const formData = new FormData();
  formData.append('pdf', pdfFile);
  const uploadResp = await fetch('/upload', { method: 'POST', body: formData });
  const { job_id } = await uploadResp.json();
  
  // Poll
  while (true) {
    const pollResp = await fetch(`/api/job/${job_id}/full`);
    const job = await pollResp.json();
    
    console.log(`Progress: ${(job.progress * 100).toFixed(0)}%`);
    console.log(`Stage: ${job.current_stage}`);
    
    if (['completed', 'failed', 'error'].includes(job.status)) {
      return job;
    }
    
    await new Promise(r => setTimeout(r, 1000));
  }
}
```

### Chat Integration Example

```javascript
// Send message
const chatResp = await fetch(`/api/job/${job_id}/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Why did it fail?' })
});

// Get history
const historyResp = await fetch(`/api/job/${job_id}/chat/history`);
const messages = await historyResp.json();
console.log(messages);

// Clear history
await fetch(`/api/job/${job_id}/chat/history`, { method: 'DELETE' });
```
