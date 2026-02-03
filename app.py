"""
Paper Reproducibility Checker - Flask Backend

Analyzes scientific papers for reproducibility by extracting code artifacts
and running them in isolated Docker containers with an LLM agent.
"""

import os
import json
import uuid
import sqlite3
import threading
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, Response, render_template
from anthropic import Anthropic
import pdfplumber
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Initialize Anthropic client with explicit API key
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
client = Anthropic(api_key=api_key)

# Configuration
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DATABASE = "reproducibility.db"
MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB

# In-memory event queues for SSE connections
# {job_id: [events]}
event_queues = {}
event_queues_lock = threading.Lock()


# ============================================================================
# Database Initialization
# ============================================================================

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            pdf_path TEXT NOT NULL,
            pdf_filename TEXT,
            report JSON,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            url TEXT,
            artifact_type TEXT,
            description TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    conn.commit()
    conn.close()


def emit_event(job_id, event_dict):
    """Emit event to all SSE clients watching this job."""
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    
    with event_queues_lock:
        if job_id in event_queues:
            event_queues[job_id].append(event_dict)
            app.logger.info(f"[{job_id}] Event: {event_dict['step']} - {event_dict['message']}")


# ============================================================================
# PDF Processing
# ============================================================================

def extract_pdf_text(pdf_path, max_chars=50000):
    """Extract text from PDF file."""
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                if len(text) >= max_chars:
                    break
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {i+1} ---\n{page_text}"
        
        return text
    except Exception as e:
        raise Exception(f"Failed to extract PDF: {str(e)}")


def parse_paper_with_claude(pdf_text):
    """
    Use Claude to extract code artifacts and reproducibility aspects from paper.
    
    Returns:
        {
            "artifacts": [{"url": "...", "type": "...", "description": "..."}],
            "reproducibility_aspects": {...}
        }
    """
    
    prompt = f"""Analyze this scientific paper and extract:

1. **Code artifacts**: GitHub repos, datasets, supplementary code, Docker images
   - Include URLs, file links, or descriptions of where to find code
   
2. **Reproducibility aspects**:
   - Are hyperparameters documented?
   - Is dataset description sufficient?
   - Are implementation details provided?
   - Any known limitations or environment requirements?

Return valid JSON (no markdown, just JSON):
{{
  "artifacts": [
    {{"url": "https://...", "type": "github_repo|dataset|supplementary|docker|other", "description": "..."}},
  ],
  "reproducibility_aspects": {{
    "hyperparameters_documented": true/false,
    "dataset_description": "brief summary or null",
    "implementation_details": "sufficient|partial|missing",
    "environment_requirements": "description or null",
    "notes": "any other relevant info"
  }},
  "summary": "brief analysis of reproducibility"
}}

Paper text:
{pdf_text[:20000]}
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Extract JSON from response
        response_text = response.content[0].text
        
        # Try to parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # If Claude wrapped in markdown, extract it
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                result = json.loads(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                result = json.loads(json_str)
            else:
                raise ValueError(f"Could not parse Claude response: {response_text}")
        
        return result
    
    except Exception as e:
        raise Exception(f"Claude parsing failed: {str(e)}")


# ============================================================================
# Flask Routes - Core API
# ============================================================================

@app.route("/")
def index():
    """Home page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """
    Upload PDF for analysis.
    
    Returns:
        {"job_id": "...", "message": "..."}
    """
    
    # Validate file
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400
    
    file = request.files["pdf"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a PDF"}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_PDF_SIZE:
        return jsonify({"error": "PDF too large (max 100MB)"}), 400
    
    # Create job
    job_id = str(uuid.uuid4())
    pdf_filename = f"{job_id}.pdf"
    pdf_path = UPLOAD_FOLDER / pdf_filename
    
    file.save(pdf_path)
    
    # Store in DB
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO jobs (id, status, pdf_path, pdf_filename) VALUES (?, ?, ?, ?)",
        (job_id, "pending", str(pdf_path), file.filename)
    )
    conn.commit()
    conn.close()
    
    # Start background analysis thread
    thread = threading.Thread(
        target=analyze_paper_background,
        args=(job_id, str(pdf_path)),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "message": "Paper uploaded successfully. Analysis starting..."
    }), 202


@app.route("/events/<job_id>")
def events(job_id):
    """
    Server-Sent Events endpoint for streaming job progress.
    
    Frontend opens EventSource connection here to receive live updates.
    """
    
    def generate():
        # Create queue for this SSE connection
        q = []
        with event_queues_lock:
            event_queues[job_id] = q
        
        try:
            sent_complete = False
            while not sent_complete:
                if q:
                    event = q.pop(0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    if event.get("step") == "complete" or event.get("step") == "error":
                        sent_complete = True
                else:
                    time.sleep(0.1)
            
            # Keep connection open for 30 more seconds after completion
            time.sleep(2)
        
        finally:
            with event_queues_lock:
                if job_id in event_queues:
                    del event_queues[job_id]
    
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@app.route("/job/<job_id>")
def get_job(job_id):
    """Get job status and report."""
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    conn.close()
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    response = {
        "id": job["id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"]
    }
    
    if job["report"]:
        response["report"] = json.loads(job["report"])
    
    if job["error_message"]:
        response["error"] = job["error_message"]
    
    return jsonify(response)


@app.route("/jobs")
def list_jobs():
    """List all jobs (with summary)."""
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, status, pdf_filename, created_at, completed_at
        FROM jobs
        ORDER BY created_at DESC
        LIMIT 50
    """)
    jobs = c.fetchall()
    conn.close()
    
    return jsonify([dict(job) for job in jobs])


# ============================================================================
# Agent API - Backend provides Claude reasoning to agent
# ============================================================================

@app.route("/api/agent/think", methods=["POST"])
def agent_think():
    """
    Agent calls this to ask Claude what to do next.
    
    Request body:
        {
            "job_id": "...",
            "repo_state": {...}  # Current repo state from agent
        }
    
    Returns:
        {
            "action": "read_file|run_command|check_success|done",
            "target": "path or command",
            "reasoning": "why",
            "check_for": "output pattern to check (optional)"
        }
    """
    
    data = request.json
    job_id = data.get("job_id")
    repo_state = data.get("repo_state", {})
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    try:
        # Build prompt for Claude
        prompt = f"""You are an agent inside a Docker container attempting to reproduce a code artifact.

Your goal: Clone the repository, understand how to run it, and execute it successfully.

Current state:
- Files in repo: {repo_state.get('files', [])[:20]}
- Current directory: {repo_state.get('cwd', '/workspace/repo')}
- Last command output: {repo_state.get('last_output', {}).get('stdout', '')[:500]}
- Last command error: {repo_state.get('last_output', {}).get('stderr', '')[:500]}
- Completed steps: {repo_state.get('completed_steps', [])}
- Errors so far: {repo_state.get('errors', [])}

Next, decide what to do. Return JSON (valid JSON only, no markdown):
{{
  "action": "read_file" | "run_command" | "check_success" | "done",
  "target": "path/to/file or shell command",
  "reasoning": "brief explanation why",
  "check_for": "pattern to check in output (optional)"
}}

Guidelines:
1. Always start by reading README.md if present
2. Look for setup.py, requirements.txt, environment.yml, or similar
3. Try to understand what this code does
4. Install dependencies if needed
5. Run the main script/notebook
6. If you see errors, try to fix them (install missing packages, adjust paths, etc.)
7. Stop after successful execution or if you're stuck

Start now. What's your first action?
"""
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text
        
        # Parse JSON
        try:
            action = json.loads(response_text)
        except json.JSONDecodeError:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                action = json.loads(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                action = json.loads(json_str)
            else:
                # Return default action
                action = {
                    "action": "done",
                    "reasoning": "Could not parse Claude response"
                }
        
        return jsonify(action)
    
    except Exception as e:
        app.logger.error(f"Error in agent/think: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/log", methods=["POST"])
def agent_log():
    """Agent logs progress back to backend."""
    
    data = request.json
    job_id = data.get("job_id")
    message = data.get("message", "")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # Emit to frontend via SSE
    emit_event(job_id, {
        "step": "agent_progress",
        "message": message
    })
    
    return jsonify({"ok": True})


# ============================================================================
# Background Job Processing
# ============================================================================

def analyze_paper_background(job_id, pdf_path):
    """Main background job: analyze paper for reproducibility."""
    
    try:
        emit_event(job_id, {
            "step": "starting",
            "message": "Analysis starting...",
            "progress": 0
        })
        
        # Update DB status
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE jobs SET status = ? WHERE id = ?", ("processing", job_id))
        conn.commit()
        conn.close()
        
        # Step 1: Extract PDF text
        emit_event(job_id, {
            "step": "extracting_pdf",
            "message": "Extracting text from PDF...",
            "progress": 10
        })
        
        pdf_text = extract_pdf_text(pdf_path)
        emit_event(job_id, {
            "step": "pdf_extracted",
            "message": f"Extracted {len(pdf_text)} characters from PDF",
            "progress": 20
        })
        
        # Step 2: Parse paper with Claude
        emit_event(job_id, {
            "step": "parsing_paper",
            "message": "Analyzing paper with Claude...",
            "progress": 25
        })
        
        paper_info = parse_paper_with_claude(pdf_text)
        
        # Store artifacts in DB
        artifacts = paper_info.get("artifacts", [])
        conn = get_db()
        c = conn.cursor()
        for artifact in artifacts:
            c.execute(
                """INSERT INTO artifacts (job_id, url, artifact_type, description)
                   VALUES (?, ?, ?, ?)""",
                (job_id, artifact.get("url"), artifact.get("type"), artifact.get("description"))
            )
        conn.commit()
        conn.close()
        
        emit_event(job_id, {
            "step": "paper_parsed",
            "message": f"Found {len(artifacts)} code artifacts",
            "progress": 40,
            "artifacts": artifacts
        })
        
        # Step 3: Prepare report
        report = {
            "code_found": len(artifacts) > 0,
            "artifacts": artifacts,
            "reproducibility_aspects": paper_info.get("reproducibility_aspects", {}),
            "summary": paper_info.get("summary", "")
        }
        
        # Save report to DB
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """UPDATE jobs SET status = ?, report = ?, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            ("completed", json.dumps(report), job_id)
        )
        conn.commit()
        conn.close()
        
        emit_event(job_id, {
            "step": "complete",
            "message": "Analysis complete",
            "progress": 100,
            "report": report
        })
        
        app.logger.info(f"Job {job_id} completed successfully")
    
    except Exception as e:
        app.logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        
        emit_event(job_id, {
            "step": "error",
            "message": f"Error: {str(e)}",
            "error": True
        })
        
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """UPDATE jobs SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            ("error", str(e), job_id)
        )
        conn.commit()
        conn.close()


# ============================================================================
# Application Startup
# ============================================================================

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
