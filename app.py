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
import hashlib
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
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            step TEXT,
            message TEXT,
            severity TEXT DEFAULT 'info',
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            extracted_text TEXT,
            claimed_results JSON,
            methodology TEXT,
            dependencies TEXT,
            dataset_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS execution_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            commands_run TEXT,
            stdout_combined TEXT,
            actual_results JSON,
            dependencies_used TEXT,
            errors_summary TEXT,
            discovered_files JSON,
            test_info TEXT,
            randomness_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    # Add missing columns to existing databases (backward compatibility)
    try:
        c.execute("ALTER TABLE execution_details ADD COLUMN discovered_files JSON")
    except:
        pass  # Column already exists
    try:
        c.execute("ALTER TABLE execution_details ADD COLUMN test_info TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE execution_details ADD COLUMN randomness_info TEXT")
    except:
        pass
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS aspect_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            aspect_id TEXT NOT NULL,
            name TEXT,
            status TEXT,
            evidence TEXT,
            paper_supports BOOLEAN,
            code_supports BOOLEAN,
            conclusion TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    # Cache tables for pipeline stages
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_paper_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_hash TEXT UNIQUE NOT NULL,
            extracted_text TEXT,
            claimed_results JSON,
            methodology TEXT,
            dependencies TEXT,
            dataset_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_code_execution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            repo_hash TEXT NOT NULL,
            commands_run TEXT,
            stdout_combined TEXT,
            actual_results JSON,
            dependencies_used TEXT,
            errors_summary TEXT,
            discovered_files JSON,
            test_info TEXT,
            randomness_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_url, repo_hash)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_evaluation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_hash TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            evaluations JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(paper_hash, code_hash)
        )
    """)
    
    conn.commit()
    conn.close()


def emit_event(job_id, event_dict):
    """Emit event to all SSE clients watching this job and store in database."""
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    
    # Store event in database for later retrieval
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO events (job_id, timestamp, step, message, severity)
            VALUES (?, ?, ?, ?, ?)
        """, (
            job_id,
            event_dict["timestamp"],
            event_dict.get("step", "unknown"),
            event_dict.get("message", ""),
            event_dict.get("severity", "info")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.error(f"[{job_id}] Failed to store event: {e}")
    
    # Emit to SSE clients
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
    Caches results by repo URL to skip redundant executions.
    """
    # Check cache: if we've analyzed this repo before, reuse results
    cache_key = hashlib.md5(repo_url.encode()).hexdigest()
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM execution_details WHERE job_id IN (SELECT id FROM jobs WHERE report LIKE ?)",
        (f'%"url": "{repo_url}"%',)
    )
    cached = c.fetchone()
    conn.close()
    
    if cached:
        app.logger.info(f"[{job_id}] Cache hit for {repo_url} - reusing execution results")
        emit_event(job_id, {
            "step": "cache_hit",
            "message": f"Using cached results for {repo_url}"
        })
        # Copy cached results to new job
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO execution_details 
            (job_id, commands_run, stdout_combined, actual_results, dependencies_used, errors_summary, discovered_files, test_info, randomness_info)
            SELECT ?, commands_run, stdout_combined, actual_results, dependencies_used, errors_summary, discovered_files, test_info, randomness_info
            FROM execution_details WHERE id = ?
        """, (job_id, cached['id']))
        conn.commit()
        conn.close()
        
        emit_event(job_id, {
            "step": "agent_completed",
            "message": "Cached agent results applied"
        })
        return True
    
    if not DOCKER_AVAILABLE:
        app.logger.error("Docker not available")
        emit_event(job_id, {
            "step": "error",
            "message": "Docker not available for agent execution"
        })
        return False
    
    try:
        container_name = f"agent-{job_id[:8]}"  # Shorter name for readability
        
        app.logger.info(f"[{job_id}] === Agent Container Spawn ===")
        app.logger.info(f"[{job_id}] Repository: {repo_url}")
        
        # Determine backend URL for agent
        # Both Flask app and agent run on workspace_traefik network
        # Agent reaches Flask app by container name: http://paper-reproducibility:5000
        backend_url = "http://paper-reproducibility:5000"
        
        app.logger.info(f"[{job_id}] Backend URL for agent: {backend_url} (via Docker network)")
        app.logger.info(f"[{job_id}] Container name: {container_name}")
        
        emit_event(job_id, {
            "step": "spawning_agent",
            "message": f"Spawning agent container for: {repo_url}"
        })
        
        # Verify image exists
        try:
            docker_client.images.get("paper-reproducibility-agent:latest")
            app.logger.info(f"[{job_id}] Agent image verified: paper-reproducibility-agent:latest")
        except Exception as e:
            app.logger.warning(f"[{job_id}] Agent image not found, attempting build: {e}")
            build_agent_image()
        
        # Run agent container
        app.logger.info(f"[{job_id}] Starting container with:")
        app.logger.info(f"[{job_id}]   Memory: 2GB")
        app.logger.info(f"[{job_id}]   CPU: 2 cores (nano_cpus={int(2 * 1e9)})")
        app.logger.info(f"[{job_id}]   Network: workspace_traefik (shared with Flask app)")
        
        # Note: nano_cpus = CPU count * 1e9 (1 CPU = 1e9 nano_cpus)
        # Use detach=True to get container object (then we can stream logs)
        container = docker_client.containers.run(
            "paper-reproducibility-agent:latest",
            detach=True,  # Use True to get container object
            name=container_name,
            environment={
                "REPO_URL": repo_url,
                "JOB_ID": job_id,
                "BACKEND_URL": backend_url,
                "ANTHROPIC_API_KEY": api_key
            },
            mem_limit="2g",
            memswap_limit="2g",
            nano_cpus=int(2 * 1e9),  # 2 CPU cores
            # Add agent to workspace_traefik network (same as Flask app)
            # This allows agent to reach Flask app by container name
            network="workspace_traefik",
            remove=False,  # Manual cleanup to avoid race conditions
            stdout=True,
            stderr=True
        )
        app.logger.info(f"[{job_id}] Container created and started: {container.id[:12]}")
        
        try:
            # Wait for container to complete and stream logs
            app.logger.info(f"[{job_id}] Waiting for container to complete...")
            line_count = 0
            for line in container.logs(stream=True):
                message = line.decode('utf-8').strip()
                if message:
                    line_count += 1
                    app.logger.info(f"[{job_id}] [Agent] {message}")
                    emit_event(job_id, {
                        "step": "agent_output",
                        "message": message
                    })
            
            # Wait for container to exit and check status
            app.logger.info(f"[{job_id}] Container logs complete, checking exit status...")
            result = container.wait(timeout=30)
            exit_code = result.get("StatusCode", -1)
            app.logger.info(f"[{job_id}] Container exited with code: {exit_code}")
            
            app.logger.info(f"[{job_id}] Container execution complete ({line_count} lines of output)")
            
            emit_event(job_id, {
                "step": "agent_completed",
                "message": "Agent completed analysis"
            })
            
            app.logger.info(f"[{job_id}] === Agent Container Success ===")
            
        finally:
            # Manual cleanup (safe to call even if container already removed)
            try:
                container.reload()  # Refresh container state
                app.logger.info(f"[{job_id}] Cleaning up container {container.id[:12]}...")
                container.stop(timeout=5)
                container.remove()
                app.logger.info(f"[{job_id}] Container cleaned up successfully")
            except docker.errors.NotFound:
                app.logger.info(f"[{job_id}] Container already removed (expected)")
            except Exception as e:
                app.logger.warning(f"[{job_id}] Container cleanup warning: {e}")
        
        return True
    
    except Exception as e:
        app.logger.error(f"[{job_id}] === Agent Container Failed ===")
        app.logger.error(f"[{job_id}] Exception type: {type(e).__name__}")
        app.logger.error(f"[{job_id}] Error message: {str(e)}")
        
        # Try to clean up on failure too
        try:
            if 'container' in locals():
                container.stop(timeout=5)
                container.remove()
        except Exception:
            pass
        
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
        app.logger.info(f"Extracting PDF: {pdf_path}")
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            app.logger.info(f"PDF has {total_pages} pages")
            for i, page in enumerate(pdf.pages):
                if len(text) >= max_chars:
                    app.logger.info(f"Reached max_chars limit at page {i+1}")
                    break
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {i+1} ---\n{page_text}"
                    if (i + 1) % 5 == 0:
                        app.logger.info(f"Extracted {i+1}/{total_pages} pages, {len(text)} chars so far")
        
        app.logger.info(f"PDF extraction complete: {len(text)} characters from {total_pages} pages")
        return text
    except Exception as e:
        app.logger.error(f"Failed to extract PDF: {str(e)}", exc_info=True)
        raise Exception(f"Failed to extract PDF: {str(e)}")


def store_paper_analysis(job_id: str, paper_info: dict, pdf_text: str):
    """Store paper analysis for later evaluation."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO paper_analysis 
            (job_id, extracted_text, claimed_results, methodology, dependencies, dataset_description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            pdf_text[:50000],  # Store first 50k chars of PDF text
            json.dumps(paper_info.get("claimed_results", {})),
            paper_info.get("methodology", ""),
            paper_info.get("dependencies", ""),
            paper_info.get("dataset_description", "")
        ))
        conn.commit()
        conn.close()
        app.logger.info(f"[{job_id}] Stored paper analysis in database")
    except Exception as e:
        app.logger.error(f"[{job_id}] Failed to store paper analysis: {e}")


def parse_paper_with_claude(pdf_text):
    """
    Use Claude to extract code artifacts and reproducibility aspects from paper.
    
    Returns:
        {
            "artifacts": [{"url": "...", "type": "...", "description": "..."}],
            "reproducibility_aspects": {...}
        }
    """
    
    app.logger.info(f"Parsing paper with Claude (model: {CLAUDE_MODEL}, input: {len(pdf_text)} chars)")
    
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
        app.logger.info(f"Calling Claude API with max_tokens=2000")
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
        app.logger.info(f"Claude response received: {len(response_text)} chars")
        
        # Try to parse JSON
        try:
            app.logger.info(f"Parsing Claude response as JSON")
            result = json.loads(response_text)
            app.logger.info(f"Successfully parsed JSON with {len(result.get('artifacts', []))} artifacts")
        except json.JSONDecodeError:
            app.logger.info(f"Direct JSON parsing failed, trying to extract from markdown")
            # If Claude wrapped in markdown, extract it
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                result = json.loads(json_str)
                app.logger.info(f"Extracted JSON from markdown code block")
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                result = json.loads(json_str)
                app.logger.info(f"Extracted JSON from plain code block")
            else:
                raise ValueError(f"Could not parse Claude response: {response_text}")
        
        return result
    
    except Exception as e:
        app.logger.error(f"Claude parsing failed: {str(e)}", exc_info=True)
        raise Exception(f"Claude parsing failed: {str(e)}")


# ============================================================================
# Flask Routes - Core API
# ============================================================================

@app.route("/")
def index():
    """Home page - upload form."""
    return render_template("index.html")


@app.route("/history")
def history():
    """History page - browse past analyses."""
    return render_template("history.html")


@app.route("/about")
def about():
    """About page - project information."""
    return render_template("about.html")


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


@app.route("/api/job/<job_id>/full", methods=["GET"])
def get_job_full(job_id):
    """Get full job data including events, artifacts, and reproducibility aspects."""
    
    conn = get_db()
    c = conn.cursor()
    
    # Fetch job
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    
    if not job:
        conn.close()
        return jsonify({"error": "Job not found"}), 404
    
    # Fetch all events
    c.execute("""
        SELECT timestamp, step, message, severity
        FROM events
        WHERE job_id = ?
        ORDER BY timestamp ASC
    """, (job_id,))
    events_list = [dict(row) for row in c.fetchall()]
    
    # Fetch artifacts
    c.execute("""
        SELECT url, artifact_type, description
        FROM artifacts
        WHERE job_id = ?
    """, (job_id,))
    artifacts = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    # Parse report
    report = {}
    if job["report"]:
        report = json.loads(job["report"])
    
    response = {
        "id": job["id"],
        "status": job["status"],
        "pdf_filename": job["pdf_filename"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "report": report,
        "error_message": job["error_message"],
        "events": events_list,
        "artifacts": artifacts
    }
    
    return jsonify(response)


@app.route("/reports/<job_id>")
def detail_page(job_id):
    """Serve detail page for a job."""
    return render_template("detail.html", job_id=job_id)


@app.route("/results/<job_id>")
def results_page(job_id):
    """Serve results page for a job (alias for detail)."""
    return render_template("detail.html", job_id=job_id)


@app.route("/job/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    """Delete a job and all related data."""
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Get job to find PDF path
        c.execute("SELECT pdf_path FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        
        if not job:
            conn.close()
            return jsonify({"error": "Job not found"}), 404
        
        # Delete PDF file
        if job["pdf_path"]:
            pdf_file = Path(job["pdf_path"])
            if pdf_file.exists():
                pdf_file.unlink()
                app.logger.info(f"[{job_id}] Deleted PDF file: {job['pdf_path']}")
        
        # Delete from database
        c.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
        c.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
        c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        
        app.logger.info(f"[{job_id}] Job deleted successfully")
        
        return jsonify({"ok": True, "message": "Job deleted"})
        
    except Exception as e:
        app.logger.error(f"[{job_id}] Failed to delete job: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Cache Management
# ============================================================================

@app.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    """Get cache statistics."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) as count FROM cache_paper_analysis")
        paper_row = c.fetchone()
        paper_count = paper_row["count"] if paper_row else 0
        
        c.execute("SELECT COUNT(*) as count FROM cache_code_execution")
        code_row = c.fetchone()
        code_count = code_row["count"] if code_row else 0
        
        c.execute("SELECT COUNT(*) as count FROM cache_evaluation")
        eval_row = c.fetchone()
        eval_count = eval_row["count"] if eval_row else 0
        
        total = paper_count + code_count + eval_count
        app.logger.info(f"Cache stats: paper={paper_count}, code={code_count}, eval={eval_count}, total={total}")
        
        conn.close()
        
        return jsonify({
            "paper_analysis": paper_count,
            "code_execution": code_count,
            "evaluation": eval_count,
            "total": total
        })
    except Exception as e:
        app.logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        return jsonify({"paper_analysis": 0, "code_execution": 0, "evaluation": 0, "total": 0, "error": str(e)}), 200


@app.route("/api/cache/clear", methods=["DELETE"])
def cache_clear():
    """Clear all cache tables."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute("DELETE FROM cache_paper_analysis")
        c.execute("DELETE FROM cache_code_execution")
        c.execute("DELETE FROM cache_evaluation")
        conn.commit()
        conn.close()
        
        app.logger.info("Cache cleared successfully")
        return jsonify({"ok": True, "message": "Cache cleared"})
    except Exception as e:
        app.logger.error(f"Failed to clear cache: {e}")
        return jsonify({"error": str(e)}), 500


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
        # Use `or []` to handle both missing keys AND None values
        files_list = (repo_state.get("discovered_files") or [])[:15]
        last_output = repo_state.get("last_output") or ""
        errors = repo_state.get("errors") or []
        iteration = repo_state.get("iteration", 0)
        
        # Summarize last output (truncate to prevent context explosion)
        # Increased from 300 to 2000 chars so agent can see completion messages
        last_output_summary = last_output[:2000] if last_output else "(none)"
        if len(last_output) > 2000:
            last_output_summary = last_output[:2000] + "... [truncated]"
        
        # Summarize errors (only recent ones)
        error_lines = []
        if errors:
            recent_errors = errors[-2:]  # Last 2 errors only
            for e in recent_errors:
                cmd = e.get('command', 'unknown')
                stderr = e.get('stderr', 'unknown')[:100]
                error_lines.append(f"  - {cmd}: {stderr}")
        
        error_section = ("Recent errors:\n" + "\n".join(error_lines)) if error_lines else "- No errors yet"
        
        # Build prompt for Claude
        prompt = f"""You are an agent inside a Docker container attempting to reproduce a code artifact.

GOAL: Clone the repository, understand how to run it, and execute it successfully.

CURRENT STATE:
- Repository: {repo_state.get('repo_url', 'unknown')}
- Files in root: {files_list}
- Iteration: {iteration}/15
- Last command output (truncated): {last_output_summary}
- Errors encountered: {len(errors)} total
{error_section}

IMPORTANT: All commands are executed in a BASH shell with full shell features enabled.
You CAN use:
  - Pipes: | (e.g., pip list | grep numpy)
  - Redirects: >, >>, 2>&1 (e.g., pip install -r requirements.txt 2>&1 | tail -20)
  - Operators: && (run if success), || (run if fail)
  - Examples: python script.py && echo "Success" || echo "Failed"

INSTRUCTIONS:
1. First, always list and read README.md or similar documentation
2. Look for setup.py, requirements.txt, environment.yml, Dockerfile, or package.json
3. Understand what this code does and what dependencies it needs
4. Install all required dependencies (pip, conda, apt-get, etc.)
5. Find and run the main script, notebook, or application
6. Once working, report success with check_success action
7. If stuck, try different approaches (different Python versions, skip optional deps, etc.)

DEPENDENCY CONFLICT HANDLING:
- If you see "requires X>=Y.Z but you have X==A.B", you MUST fix this!
- Option 1: Install a compatible version that satisfies all requirements
- Option 2: Check if only some dependencies are optional/needed
- Option 3: Try a different Python version (e.g., python3.9 vs python3.11)
- AVOID: Going in circles (trying same versions repeatedly)

ENVIRONMENT:
- Container has Python 3.11 pre-installed
- You CAN modify requirements files if needed
- You CAN create virtual environments if needed
- You MUST resolve dependency conflicts before running code

RESPONSE FORMAT:
Return ONLY valid JSON (no markdown, plain JSON):
{{
  "action": "read_file" | "run_command" | "check_success" | "done",
  "target": "path/to/file or shell command",
  "reasoning": "brief explanation of why you're doing this"
}}

Action meanings:
- read_file: Read and understand a file
- run_command: Execute a shell command (full bash syntax supported)
- check_success: Confirm execution succeeded
- done: Finished analysis (success or gave up after many attempts)

Good shell command examples:
  - pip install -r requirements.txt 2>&1 | head -30
  - python script.py || echo "Command failed with exit code: $?"
  - grep -r "def main" . --include="*.py"
  - cat requirements.txt | grep -i numpy

Current iteration: {iteration}/15
Last output: {last_output_summary if last_output_summary != "(none)" else "No output yet"}

What should the agent do next?
"""
        
        # Use Haiku for agent reasoning (simple decisions, save tokens)
        response = client.messages.create(
            model="claude-3-5-haiku",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text
        
        # Log full response for debugging (not truncated!)
        app.logger.info(f"[{job_id}] === Claude Response (Full, {len(response_text)} chars) ===")
        app.logger.info(f"[{job_id}] {response_text}")
        app.logger.info(f"[{job_id}] === End Claude Response ===")
        
        # Parse JSON with detailed logging
        action = None
        
        # Try 1: Direct JSON parsing
        try:
            action = json.loads(response_text)
            app.logger.info(f"[{job_id}] ✓ Parsed JSON directly (Method 1)")
        except json.JSONDecodeError as e:
            app.logger.warning(f"[{job_id}] ✗ Direct JSON parsing failed: {str(e)}")
            
            # Try 2: Extract from ```json code block
            if "```json" in response_text:
                try:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    action = json.loads(json_str)
                    app.logger.info(f"[{job_id}] ✓ Extracted JSON from ```json block (Method 2)")
                except Exception as e2:
                    app.logger.warning(f"[{job_id}] ✗ Method 2 failed: {str(e2)}")
            
            # Try 3: Extract from plain ``` code block
            if not action and "```" in response_text:
                try:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                    action = json.loads(json_str)
                    app.logger.info(f"[{job_id}] ✓ Extracted JSON from ``` block (Method 3)")
                except Exception as e3:
                    app.logger.warning(f"[{job_id}] ✗ Method 3 failed: {str(e3)}")
            
            # Try 4: Find JSON object in response
            if not action and "{" in response_text:
                try:
                    json_start = response_text.index("{")
                    # Try progressively shorter substrings
                    for json_end in range(len(response_text), json_start, -1):
                        try:
                            potential_json = response_text[json_start:json_end]
                            action = json.loads(potential_json)
                            app.logger.info(f"[{job_id}] ✓ Found valid JSON substring (Method 4, {json_end - json_start} chars)")
                            break
                        except:
                            continue
                    
                    if not action:
                        app.logger.warning(f"[{job_id}] ✗ Method 4 failed: No valid JSON substring found")
                except Exception as e4:
                    app.logger.warning(f"[{job_id}] ✗ Method 4 failed: {str(e4)}")
            
            # If all parsing failed, return default
            if not action:
                app.logger.error(f"[{job_id}] ✗ ALL PARSING METHODS FAILED!")
                app.logger.error(f"[{job_id}] Response text: {response_text[:500]}")
                app.logger.error(f"[{job_id}] Response length: {len(response_text)}")
                app.logger.error(f"[{job_id}] Response contains '{{': {'{'  in response_text}")
                app.logger.error(f"[{job_id}] Response contains '```': {'```' in response_text}")
                
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


@app.route("/api/agent/execution", methods=["POST"])
def agent_execution():
    """Agent stores execution details for later evaluation."""
    
    data = request.json
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO execution_details 
            (job_id, commands_run, stdout_combined, actual_results, dependencies_used, errors_summary, discovered_files, test_info, randomness_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            data.get("commands_run", ""),
            data.get("stdout_combined", ""),
            json.dumps(data.get("actual_results", {})),
            data.get("dependencies_used", ""),
            data.get("errors_summary", ""),
            json.dumps(data.get("discovered_files", [])),
            data.get("test_info", ""),
            data.get("randomness_info", "")
        ))
        conn.commit()
        conn.close()
        
        app.logger.info(f"[{job_id}] Stored execution details in database")
        
        return jsonify({"ok": True})
        
    except Exception as e:
        app.logger.error(f"[{job_id}] Failed to store execution details: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/complete", methods=["POST"])
def agent_complete():
    """
    Agent calls this to report success/failure and terminate.
    
    Request body:
        {
            "job_id": "...",
            "success": true|false,
            "message": "completion message",
            "accuracy": 0.93,  # Optional: reproducibility score
            "reproducibility_aspects": {...}  # Optional: extensible aspects array
        }
    """
    
    data = request.json
    job_id = data.get("job_id")
    success = data.get("success", False)
    message = data.get("message", "Analysis complete")
    accuracy = data.get("accuracy")
    aspects = data.get("reproducibility_aspects")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    try:
        # Build result report
        report = {
            "status": "success" if success else "failed",
            "message": message,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        if accuracy is not None:
            report["reproducibility_score"] = accuracy
        
        if aspects is not None:
            report["reproducibility_aspects"] = aspects
        
        # Update database - Store execution report but don't mark completed yet
        # (Completion happens after stage 3 evaluation)
        conn = get_db()
        c = conn.cursor()
        
        # Only mark as failed if agent failed
        if not success:
            c.execute(
                """UPDATE jobs SET status = ?, error_message = ? WHERE id = ?""",
                ("failed", message, job_id)
            )
        # If success, keep status as "processing" - stage 3 will mark it "completed"
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"[{job_id}] Agent reported {'SUCCESS' if success else 'FAILURE'}: {message}")
        
        # Don't emit "complete" here - that happens after stage 3 evaluation
        # Just emit agent completion status
        emit_event(job_id, {
            "step": "agent_finished",
            "message": f"Agent finished: {message}",
            "status": "success" if success else "failed"
        })
        
        # Log final summary
        app.logger.info(f"[{job_id}] === AGENT ANALYSIS COMPLETE ===")
        app.logger.info(f"[{job_id}] Status: {'✓ SUCCESS' if success else '✗ FAILED'}")
        app.logger.info(f"[{job_id}] Message: {message}")
        if accuracy is not None:
            app.logger.info(f"[{job_id}] Reproducibility Score: {accuracy:.2%}")
        
        # Note: Aspect evaluation is triggered from analyze_paper_background, not here
        # This endpoint is just for the agent to report completion
        
        return jsonify({
            "ok": True,
            "status": "success" if success else "failed"
        })
        
    except Exception as e:
        app.logger.error(f"[{job_id}] Error in agent_complete: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Aspect Evaluation (Stage 3 of pipeline)
# ============================================================================

def evaluate_reproducibility_aspects(job_id: str, stage3_start: float = None):
    """
    STAGE 3: Evaluate aspects using all available context.
    Runs after agent completes successfully.
    
    Args:
        job_id: Job identifier
        stage3_start: Unix timestamp when stage 3 started (for timing)
    """
    if stage3_start is None:
        stage3_start = time.time()
    
    try:
        app.logger.info(f"[{job_id}] === STAGE 3: Aspect Evaluation Starting ===")
        
        # Fetch all data
        conn = get_db()
        c = conn.cursor()
        
        # Get paper analysis
        c.execute("SELECT * FROM paper_analysis WHERE job_id = ?", (job_id,))
        paper_analysis_row = c.fetchone()
        
        # Get execution details
        c.execute("SELECT * FROM execution_details WHERE job_id = ?", (job_id,))
        execution_details_row = c.fetchone()
        
        # Get artifacts
        c.execute("SELECT url, artifact_type, description FROM artifacts WHERE job_id = ?", (job_id,))
        artifacts = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        if not paper_analysis_row or not execution_details_row:
            app.logger.warning(f"[{job_id}] Missing paper or execution data for evaluation")
            emit_event(job_id, {
                "step": "evaluation_skipped",
                "message": "Skipped: Missing required data for evaluation"
            })
            return
        
        # Convert rows to dicts
        paper_analysis = dict(paper_analysis_row)
        execution_details = dict(execution_details_row)
        
        # Parse JSON fields
        paper_analysis["claimed_results"] = json.loads(paper_analysis.get("claimed_results", "{}"))
        execution_details["actual_results"] = json.loads(execution_details.get("actual_results", "{}"))
        # Parse discovered_files from JSON (or use empty list if missing)
        try:
            discovered_files_json = execution_details.get("discovered_files", "[]")
            execution_details["discovered_files"] = json.loads(discovered_files_json) if isinstance(discovered_files_json, str) else (discovered_files_json or [])
        except:
            execution_details["discovered_files"] = []
        
        # Build evaluation prompt
        prompt = f"""You are evaluating the reproducibility of a scientific paper and its code implementation.

PAPER CONTENT:
═══════════════════════════════════════════════════════════
Extracted Text (first 2000 chars):
{paper_analysis.get("extracted_text", "")[:2000]}

Methodology:
{paper_analysis.get("methodology", "No methodology found")}

Claimed Results:
{json.dumps(paper_analysis.get("claimed_results", {}), indent=2)}

Dependencies:
{paper_analysis.get("dependencies", "No dependencies mentioned")}

Dataset:
{paper_analysis.get("dataset_description", "No dataset description")}

CODE EXECUTION:
═══════════════════════════════════════════════════════════
Artifacts Found:
{json.dumps(artifacts, indent=2)}

Files in Repository:
{json.dumps(execution_details.get("discovered_files", [])[:20], default=str)}

Test Suite Information:
{execution_details.get("test_info", "No test info")}

Randomness Seed Information:
{execution_details.get("randomness_info", "No randomness info")}

Commands Run:
{execution_details.get("commands_run", "No commands recorded")[:1000]}

Execution Output (last 1500 chars):
{execution_details.get("stdout_combined", "No output recorded")[-1500:]}

Actual Results:
{json.dumps(execution_details.get("actual_results", {}), indent=2)}

Dependencies Used:
{execution_details.get("dependencies_used", "No dependencies logged")}

Errors Summary:
{execution_details.get("errors_summary", "No errors")}

EVALUATION TASKS:
═══════════════════════════════════════════════════════════

Evaluate each aspect by comparing paper claims with code implementation and execution results.
For each aspect, determine: 
- status: "pass", "partial", or "fail"
- paper_supports: Does paper documentation support this?
- code_supports: Does code/execution support this?
- evidence: Quote or describe findings from all sources
- conclusion: Brief explanation of rating

ASPECTS TO EVALUATE:

TIER 1: CRITICAL

1. DEPENDENCIES_PINNED
   Q: Are dependencies pinned to exact versions?
   Look for: numpy==1.21.0 (pass), numpy>=1.21.0 (fail), numpy (fail)
   Files shown: {execution_details.get("dependencies_used", "")}
   Status: pass=all pinned, partial=some pinned, fail=none pinned

2. RESULTS_REPRODUCIBLE
   Q: Do execution results match paper claims?
   Paper claims: {json.dumps(paper_analysis.get("claimed_results", {}))}
   Execution achieved: {json.dumps(execution_details.get("actual_results", {}))}
   Tolerance: ±2% for accuracy metrics acceptable

3. HYPERPARAMETERS_DOCUMENTED
   Q: Are hyperparameters documented AND match paper claims?
   Paper claims: {paper_analysis.get("claimed_results", {})}
   Code uses: {execution_details.get("actual_results", {})}
   Status: pass=clearly documented, partial=some documented, fail=missing

TIER 2: HIGH VALUE

4. DATASET_AVAILABLE
   Q: Is dataset easy to obtain? Public or built-in?
   Paper describes: {paper_analysis.get("dataset_description", "")}
   Status: pass=public/built-in, partial=hard to find, fail=unclear/missing

5. ENVIRONMENT_DOCUMENTED
   Q: Are Python version, OS, dependencies clearly specified?
   Check: Paper text, code comments, requirements files, README
   Status: pass=all documented, partial=some documented, fail=missing

6. TEST_SUITE_PRESENT
   Q: Are tests included? (test_*.py, tests/ folder, pytest.ini, etc)?
   Execution log: {execution_details.get("commands_run", "")[:500]}
   Status: pass=tests found, fail=no tests found

7. CONFIG_FILE_PRESENT
   Q: Are hyperparameters in separate config file (not hardcoded)?
   Look for: config.yaml, config.json, settings.py, params.yaml
   Execution log files: {json.dumps(execution_details.get("discovered_files", [])[:15], default=str)}
   Status: pass=config file found, partial=mixed hardcoded/config, fail=all hardcoded

8. DOCUMENTATION_QUALITY
   Q: Is documentation comprehensive? (README present, inline comments, docstrings)
   Check: README existence, README length, comment density
   Status: pass=comprehensive, partial=moderate, fail=minimal/none

TIER 3: NICE-TO-HAVE

9. RANDOMNESS_CONTROLLED
   Q: Are random seeds set for reproducibility?
   Look for: np.random.seed(), tf.set_seed(), torch.manual_seed()
   Code shown: {execution_details.get("stdout_combined", "")[:1000]}
   Status: pass=seeds set, partial=some seeds, fail=no seeds

10. LICENSE_SPECIFIED
    Q: Is license specified? (LICENSE file or license in setup.py)
    Files shown: {json.dumps(execution_details.get("discovered_files", [])[:15], default=str)}
    Status: pass=license found, fail=no license

11. CONTINUOUS_INTEGRATION
    Q: Is CI/CD pipeline configured? (.github/workflows, .travis.yml, etc)
    Files shown: {json.dumps(execution_details.get("discovered_files", [])[:15], default=str)}
    Status: pass=CI found, fail=no CI

12. DATA_VERSIONING
    Q: Is dataset version/hash/commit specified (not just URL)?
    Paper describes: {paper_analysis.get("dataset_description", "")}
    Status: pass=version specified, partial=URL only, fail=unclear

13. COMPUTATIONAL_REQUIREMENTS
    Q: Are time/memory/GPU requirements documented?
    Paper text: {paper_analysis.get("methodology", "")[:500]}
    Status: pass=documented, partial=partially mentioned, fail=not documented

14. OUTPUT_FORMAT_DOCUMENTED
    Q: Is output format and meaning clearly explained?
    Paper text: {paper_analysis.get("methodology", "")[:500]}
    Status: pass=documented, partial=partially clear, fail=unclear

15. PYTHON_VERSION_COMPATIBILITY
    Q: Is code tested on multiple Python versions?
    Check: setup.py python_requires, .travis.yml/GitHub Actions matrix
    Status: pass=multiple versions tested, fail=single version only

RESPONSE FORMAT:
Return ONLY valid JSON (no markdown, no explanation, just JSON):
{{
  "evaluations": [
    {{
      "aspect_id": "dependencies_pinned",
      "name": "Dependencies Pinned",
      "status": "pass",
      "paper_supports": true,
      "code_supports": true,
      "evidence": "requirements.txt uses exact versions (numpy==1.21.0)",
      "conclusion": "All dependencies pinned to exact versions"
    }},
    ...
  ]
}}
"""

        # Log what discovered_files Claude will receive
        discovered_files_list = execution_details.get("discovered_files", [])
        app.logger.info(f"[{job_id}] === Evaluation Context ===")
        app.logger.info(f"[{job_id}] Discovered files ({len(discovered_files_list)} total): {discovered_files_list[:20]}")
        app.logger.info(f"[{job_id}] Test info: {(execution_details.get('test_info') or 'N/A')[:100]}")
        app.logger.info(f"[{job_id}] Randomness info: {(execution_details.get('randomness_info') or 'N/A')[:100]}")
        app.logger.info(f"[{job_id}] Calling Claude for aspect evaluation...")
        
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text
        app.logger.info(f"[{job_id}] Claude evaluation response: {len(response_text)} chars")
        
        # Parse response
        try:
            evaluation_results = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                evaluation_results = json.loads(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                evaluation_results = json.loads(json_str)
            else:
                raise ValueError("Could not parse evaluation response")
        
        # Store evaluation results
        conn = get_db()
        c = conn.cursor()
        
        for eval_item in evaluation_results.get("evaluations", []):
            c.execute("""
                INSERT INTO aspect_evaluations
                (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                eval_item.get("aspect_id"),
                eval_item.get("name"),
                eval_item.get("status"),
                eval_item.get("evidence"),
                eval_item.get("paper_supports"),
                eval_item.get("code_supports"),
                eval_item.get("conclusion")
            ))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"[{job_id}] Stored {len(evaluation_results.get('evaluations', []))} aspect evaluations")
        
        # Update job report with evaluations
        job_conn = get_db()
        job_c = job_conn.cursor()
        job_c.execute("SELECT report FROM jobs WHERE id = ?", (job_id,))
        job_row = job_c.fetchone()
        job_conn.close()
        
        if job_row:
            report = json.loads(job_row["report"]) if job_row["report"] else {}
            report["aspect_evaluations"] = evaluation_results.get("evaluations", [])
            
            job_conn = get_db()
            job_c = job_conn.cursor()
            job_c.execute(
                "UPDATE jobs SET report = ? WHERE id = ?",
                (json.dumps(report), job_id)
            )
            job_conn.commit()
            job_conn.close()
        
        app.logger.info(f"[{job_id}] === ASPECT EVALUATION COMPLETE ===")
        
        # Stage 3 complete
        stage3_duration = int((time.time() - stage3_start) * 1000)
        emit_event(job_id, {
            "step": "stage_3_complete",
            "stage": "reproducibility_evaluation",
            "message": "Stage 3 Complete: Evaluation finished",
            "progress": 100,
            "stage_duration_ms": stage3_duration
        })
        app.logger.info(f"[{job_id}] STAGE 3 COMPLETE in {stage3_duration}ms")
        
        # Update job status to completed now that evaluation is done
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?""",
            ("completed", job_id)
        )
        conn.commit()
        conn.close()
        
        # Fetch full report for final event
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT report FROM jobs WHERE id = ?", (job_id,))
        job_row = c.fetchone()
        conn.close()
        full_report = json.loads(job_row["report"]) if job_row and job_row["report"] else {}
        
        # Emit final completion event
        emit_event(job_id, {
            "step": "complete",
            "message": f"Analysis complete - Evaluated {len(evaluation_results.get('evaluations', []))} reproducibility aspects",
            "progress": 100,
            "report": full_report
        })
        
        app.logger.info(f"[{job_id}] === ALL STAGES COMPLETE - ANALYSIS FULLY DONE ===")
        
    except Exception as e:
        app.logger.error(f"[{job_id}] Error in aspect evaluation: {e}", exc_info=True)
        emit_event(job_id, {
            "step": "error",
            "message": f"Aspect evaluation failed: {str(e)}"
        })


# ============================================================================
# Background Job Processing
# ============================================================================

def analyze_paper_background(job_id, pdf_path):
    """Main background job: analyze paper for reproducibility."""
    
    try:
        app.logger.info(f"[{job_id}] === ANALYSIS START ===")
        emit_event(job_id, {
            "step": "starting",
            "message": "Analysis starting...",
            "progress": 0
        })
        
        # Update DB status
        app.logger.info(f"[{job_id}] Updating job status to 'processing'")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE jobs SET status = ? WHERE id = ?", ("processing", job_id))
        conn.commit()
        conn.close()
        
        # ===== STAGE 1: PAPER ANALYSIS =====
        stage1_start = time.time()
        emit_event(job_id, {
            "step": "stage_1_starting",
            "stage": "paper_analysis",
            "message": "Stage 1: Analyzing Paper...",
            "progress": 5
        })
        
        # Step 1: Extract PDF text
        app.logger.info(f"[{job_id}] Step 1: Extracting PDF text from {pdf_path}")
        emit_event(job_id, {
            "step": "extracting_pdf",
            "message": "Extracting text from PDF...",
            "progress": 10
        })
        
        pdf_text = extract_pdf_text(pdf_path)
        app.logger.info(f"[{job_id}] Successfully extracted {len(pdf_text)} characters from PDF")
        emit_event(job_id, {
            "step": "pdf_extracted",
            "message": f"Extracted {len(pdf_text)} characters from PDF",
            "progress": 20
        })
        
        # Step 2: Parse paper with Claude
        app.logger.info(f"[{job_id}] Step 2: Parsing paper with Claude (model: {CLAUDE_MODEL})")
        emit_event(job_id, {
            "step": "parsing_paper",
            "message": "Analyzing paper with Claude...",
            "progress": 25
        })
        
        paper_info = parse_paper_with_claude(pdf_text)
        
        # Store paper analysis for later evaluation
        store_paper_analysis(job_id, paper_info, pdf_text)
        
        # Store artifacts in DB
        artifacts = paper_info.get("artifacts", [])
        app.logger.info(f"[{job_id}] Found {len(artifacts)} artifacts from Claude analysis")
        
        conn = get_db()
        c = conn.cursor()
        for i, artifact in enumerate(artifacts, 1):
            app.logger.info(f"[{job_id}]   Artifact {i}: {artifact.get('type')} - {artifact.get('url')}")
            app.logger.info(f"[{job_id}]     Description: {artifact.get('description')}")
            c.execute(
                """INSERT INTO artifacts (job_id, url, artifact_type, description)
                   VALUES (?, ?, ?, ?)""",
                (job_id, artifact.get("url"), artifact.get("type"), artifact.get("description"))
            )
        conn.commit()
        conn.close()
        app.logger.info(f"[{job_id}] Stored {len(artifacts)} artifacts in database")
        
        emit_event(job_id, {
            "step": "paper_parsed",
            "message": f"Found {len(artifacts)} code artifacts",
            "progress": 40,
            "artifacts": artifacts
        })
        
        # Stage 1 complete
        stage1_duration = int((time.time() - stage1_start) * 1000)
        emit_event(job_id, {
            "step": "stage_1_complete",
            "stage": "paper_analysis",
            "message": "Stage 1 Complete: Paper analyzed",
            "progress": 40,
            "stage_duration_ms": stage1_duration
        })
        app.logger.info(f"[{job_id}] STAGE 1 COMPLETE in {stage1_duration}ms")
        
        # ===== STAGE 2: CODE EXECUTION =====
        stage2_start = time.time()
        # Step 3: Run agents for GitHub repos
        github_artifacts = [a for a in artifacts if a.get("type") == "github_repo" and a.get("url")]
        app.logger.info(f"[{job_id}] Step 3: Identified {len(github_artifacts)} GitHub repositories to analyze")
        
        emit_event(job_id, {
            "step": "stage_2_starting",
            "stage": "code_execution",
            "message": "Stage 2: Executing Code...",
            "progress": 40
        })
        
        agent_results = []
        if github_artifacts:
            emit_event(job_id, {
                "step": "preparing_agents",
                "message": f"Preparing to analyze {len(github_artifacts)} GitHub repositories..."
            })
            
            # Build agent image if needed
            if DOCKER_AVAILABLE:
                app.logger.info(f"[{job_id}] Building Docker agent image...")
                build_agent_image()
            else:
                app.logger.warning(f"[{job_id}] Docker not available - agent execution will fail")
            
            # Run agent for each GitHub repo
            for i, artifact in enumerate(github_artifacts, 1):
                repo_url = artifact.get("url")
                app.logger.info(f"[{job_id}] [{i}/{len(github_artifacts)}] Spawning agent for {repo_url}")
                emit_event(job_id, {
                    "step": "running_agent",
                    "message": f"[{i}/{len(github_artifacts)}] Running agent on {repo_url}",
                    "progress": 40 + int(50 * i / len(github_artifacts))
                })
                
                try:
                    spawn_agent_container(job_id, repo_url)
                    app.logger.info(f"[{job_id}] Agent container completed for {repo_url}")
                    agent_results.append({
                        "url": repo_url,
                        "status": "analyzed"
                    })
                except Exception as e:
                    app.logger.error(f"[{job_id}] Agent failed for {repo_url}: {e}", exc_info=True)
                    agent_results.append({
                        "url": repo_url,
                        "status": "failed",
                        "error": str(e)
                    })
        else:
            # No GitHub artifacts to analyze
            app.logger.info(f"[{job_id}] No GitHub artifacts to analyze")
            emit_event(job_id, {
                "step": "no_agents_needed",
                "message": "No code artifacts to execute"
            })
        
        # Stage 2 complete
        stage2_duration = int((time.time() - stage2_start) * 1000)
        emit_event(job_id, {
            "step": "stage_2_complete",
            "stage": "code_execution",
            "message": "Stage 2 Complete: Code executed",
            "progress": 80,
            "stage_duration_ms": stage2_duration
        })
        app.logger.info(f"[{job_id}] STAGE 2 COMPLETE in {stage2_duration}ms")
        
        # ===== STAGE 3: REPRODUCIBILITY EVALUATION =====
        stage3_start = time.time()
        emit_event(job_id, {
            "step": "stage_3_starting",
            "stage": "reproducibility_evaluation",
            "message": "Stage 3: Evaluating Reproducibility...",
            "progress": 80
        })
        
        # Trigger evaluation in background thread
        # (This will emit stage_3_complete when done)
        threading.Thread(
            target=evaluate_reproducibility_aspects,
            args=(job_id, stage3_start),
            daemon=True
        ).start()
        
        # Step 4: Evaluation triggered in background thread
        # Don't emit "complete" here - wait for evaluation thread to finish
        # (Evaluation thread will emit "complete" when done)
        app.logger.info(f"[{job_id}] Step 4: Background evaluation triggered (main thread returns)")
        app.logger.info(f"[{job_id}] === STAGE 2 DONE, STAGE 3 RUNNING IN BACKGROUND ===")
    
    except Exception as e:
        app.logger.error(f"[{job_id}] === ANALYSIS FAILED ===", exc_info=True)
        app.logger.error(f"[{job_id}] Error details: {str(e)}")
        
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
        app.logger.error(f"[{job_id}] Job marked as failed in database")


# ============================================================================
# Application Startup
# ============================================================================

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
