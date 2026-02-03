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
import docker
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

# Initialize Docker client
try:
    docker_client = docker.from_env()
    DOCKER_AVAILABLE = True
except Exception as e:
    print(f"Warning: Docker not available: {e}")
    docker_client = None
    DOCKER_AVAILABLE = False

# Configuration
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DATABASE = "reproducibility.db"
MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-1")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

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


def build_agent_image():
    """Build Docker image for agent sandbox."""
    if not DOCKER_AVAILABLE:
        return False
    
    try:
        print("Building agent Docker image...")
        docker_client.images.build(
            path=".",
            dockerfile="Dockerfile.agent",
            tag="paper-reproducibility-agent:latest",
            quiet=False
        )
        print("✓ Agent image built successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to build agent image: {e}")
        return False


def spawn_agent_container(job_id, repo_url):
    """
    Spawn Docker container to run agent on repository.
    
    Agent will clone repo, analyze it, and call backend API.
    """
    if not DOCKER_AVAILABLE:
        app.logger.error("Docker not available")
        emit_event(job_id, {
            "step": "error",
            "message": "Docker not available for agent execution"
        })
        return False
    
    try:
        container_name = f"agent-{job_id}"
        
        # Determine backend URL (localhost or host.docker.internal)
        backend_url = BACKEND_URL
        if "localhost" in backend_url or "127.0.0.1" in backend_url:
            backend_url = backend_url.replace("localhost", "host.docker.internal")
            backend_url = backend_url.replace("127.0.0.1", "host.docker.internal")
        
        emit_event(job_id, {
            "step": "spawning_agent",
            "message": f"Spawning agent container for: {repo_url}"
        })
        
        # Run agent container
        app.logger.info(f"Starting agent container: {container_name}")
        container = docker_client.containers.run(
            "paper-reproducibility-agent:latest",
            detach=False,
            name=container_name,
            environment={
                "REPO_URL": repo_url,
                "JOB_ID": job_id,
                "BACKEND_URL": backend_url,
                "ANTHROPIC_API_KEY": api_key
            },
            mem_limit="2g",
            memswap_limit="2g",
            cpus=2.0,
            network_mode="host" if os.name != "nt" else None,
            remove=True,  # Auto-cleanup on exit
            stdout=True,
            stderr=True
        )
        
        # Stream container logs
        for line in container.logs(stream=True):
            message = line.decode('utf-8').strip()
            if message:
                print(f"[Agent {job_id}] {message}")
                emit_event(job_id, {
                    "step": "agent_output",
                    "message": message
                })
        
        emit_event(job_id, {
            "step": "agent_completed",
            "message": "Agent completed analysis"
        })
        
        return True
    
    except Exception as e:
        app.logger.error(f"Failed to run agent: {e}", exc_info=True)
        emit_event(job_id, {
            "step": "error",
            "message": f"Agent execution failed: {str(e)}"
        })
        return False


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
            model=CLAUDE_MODEL,
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
            "reasoning": "why"
        }
    """
    
    data = request.json
    job_id = data.get("job_id")
    repo_state = data.get("repo_state", {})
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    try:
        # Format current state for Claude
        files_list = repo_state.get("discovered_files", [])[:15]
        last_output = repo_state.get("last_output", "")
        errors = repo_state.get("errors", [])
        iteration = repo_state.get("iteration", 0)
        
        # Build prompt for Claude
        prompt = f"""You are an agent inside a Docker container attempting to reproduce a code artifact.

GOAL: Clone the repository, understand how to run it, and execute it successfully.

CURRENT STATE:
- Repository: {repo_state.get('repo_url', 'unknown')}
- Files in root: {files_list}
- Iteration: {iteration}/15
- Last command output: {last_output[:300] if last_output else '(none)'}
- Errors encountered: {len(errors)} total
{f"- Recent error: {errors[-1] if errors else '(none)'}" if errors else ""}

INSTRUCTIONS:
1. First, always list and read README.md or similar documentation
2. Look for setup.py, requirements.txt, environment.yml, Dockerfile, or package.json
3. Understand what this code does and what dependencies it needs
4. Install all required dependencies
5. Find and run the main script, notebook, or application
6. Report success or document what failed

RESPONSE FORMAT:
Return ONLY valid JSON (no markdown, plain JSON):
{{
  "action": "read_file" | "run_command" | "check_success" | "done",
  "target": "path/to/file or shell command",
  "reasoning": "brief explanation of why you're doing this"
}}

Action meanings:
- read_file: Read and understand a file
- run_command: Execute a shell command (use absolute paths when possible)
- check_success: Confirm the execution was successful
- done: Finished (either succeeded or gave up)

Current iteration: {iteration}/15
{f'Last output: {last_output[:200]}...' if last_output else ''}

What should the agent do next?
"""
        
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text
        app.logger.info(f"[{job_id}] Claude decision: {response_text[:200]}")
        
        # Parse JSON
        try:
            action = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                action = json.loads(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                action = json.loads(json_str)
            else:
                # Last resort: return done action
                app.logger.warning(f"Could not parse Claude response: {response_text}")
                action = {
                    "action": "done",
                    "reasoning": "Could not parse Claude response, aborting"
                }
        
        return jsonify(action)
    
    except Exception as e:
        app.logger.error(f"Error in agent/think: {str(e)}")
        return jsonify({"error": str(e), "action": "done"}), 500


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
        
        # Step 3: Run agents for GitHub repos
        github_artifacts = [a for a in artifacts if a.get("type") == "github_repo" and a.get("url")]
        
        agent_results = []
        if github_artifacts:
            emit_event(job_id, {
                "step": "preparing_agents",
                "message": f"Preparing to analyze {len(github_artifacts)} GitHub repositories..."
            })
            
            # Build agent image if needed
            if DOCKER_AVAILABLE:
                build_agent_image()
            
            # Run agent for each GitHub repo
            for i, artifact in enumerate(github_artifacts, 1):
                repo_url = artifact.get("url")
                emit_event(job_id, {
                    "step": "running_agent",
                    "message": f"[{i}/{len(github_artifacts)}] Running agent on {repo_url}",
                    "progress": 40 + int(50 * i / len(github_artifacts))
                })
                
                spawn_agent_container(job_id, repo_url)
                agent_results.append({
                    "url": repo_url,
                    "status": "analyzed"
                })
        
        # Step 4: Prepare report
        report = {
            "code_found": len(artifacts) > 0,
            "artifacts": artifacts,
            "reproducibility_aspects": paper_info.get("reproducibility_aspects", {}),
            "summary": paper_info.get("summary", ""),
            "agent_results": agent_results
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
