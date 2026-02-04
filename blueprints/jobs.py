"""Jobs blueprint - upload, history, detail, results pages."""

import os
import json
import uuid
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, Response, session, redirect
from utils.decorators import require_auth
from config import Config
from services.job_service import (
    create_job, get_job, get_user_jobs, update_job_status, delete_job,
    store_artifacts, get_job_artifacts, get_job_events
)
from services.analysis_service import extract_and_analyze_pdf
from services.docker_service import spawn_agent_container
from services.evaluation_service import evaluate_reproducibility_aspects
from utils.pdf_utils import extract_page_count, generate_pdf_thumbnail
from database import get_db

jobs_bp = Blueprint('jobs', __name__)

# Event queues for SSE
event_queues = {}
event_queues_lock = threading.Lock()


def emit_event(job_id, event_dict):
    """Emit event to SSE clients and update job progress for milestone events."""
    from datetime import datetime
    from services.job_service import update_job_status
    
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    
    # Store non-chat events in database
    step = event_dict.get("step", "unknown")
    is_chat_event = step and (step.startswith("chat_") or step == "chat_error")
    
    if not is_chat_event:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                INSERT INTO events (job_id, timestamp, step, message, severity)
                VALUES (?, ?, ?, ?, ?)
            """, (
                job_id,
                event_dict["timestamp"],
                step,
                event_dict.get("message", ""),
                event_dict.get("severity", "info")
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            pass
        
        # Update job progress for milestone events
        if step == "stage_1_complete":
            update_job_status(job_id, "processing", progress=0.33)
        elif step == "stage_2_complete":
            update_job_status(job_id, "processing", progress=0.66)
        elif step == "stage_3_complete":
            update_job_status(job_id, "processing", progress=1.0)
    
    # Emit to SSE clients
    with event_queues_lock:
        if job_id in event_queues:
            event_queues[job_id].append(event_dict)


def analyze_paper_background(job_id, pdf_path, config, llm_provider):
    """Background job for paper analysis."""
    try:
        emit_event(job_id, {
            "step": "starting",
            "message": "Analysis starting...",
            "progress": 0
        })
        
        # Update status
        update_job_status(job_id, "processing")
        
        # STAGE 1: Paper analysis
        emit_event(job_id, {
            "step": "stage_1_starting",
            "message": "Stage 1: Analyzing Paper...",
            "progress": 5
        })
        
        emit_event(job_id, {
            "step": "extracting_pdf",
            "message": "Extracting text from PDF..."
        })
        
        pdf_text, paper_info = extract_and_analyze_pdf(pdf_path, job_id, llm_provider)
        
        emit_event(job_id, {
            "step": "pdf_extracted",
            "message": f"Extracted {len(pdf_text)} characters from PDF",
            "progress": 40
        })
        
        # Store artifacts
        artifacts = paper_info.get("artifacts", [])
        store_artifacts(job_id, artifacts)
        
        emit_event(job_id, {
            "step": "stage_1_complete",
            "message": f"Found {len(artifacts)} artifacts",
            "progress": 40
        })
        
        # STAGE 2: Code execution
        emit_event(job_id, {
            "step": "stage_2_starting",
            "message": "Stage 2: Executing Code...",
            "progress": 45
        })
        
        github_artifacts = [a for a in artifacts if a.get("type") == "github_repo" and a.get("url")]
        
        if github_artifacts:
            for i, artifact in enumerate(github_artifacts, 1):
                repo_url = artifact.get("url")
                emit_event(job_id, {
                    "step": "running_agent",
                    "message": f"[{i}/{len(github_artifacts)}] Running agent on {repo_url}",
                    "progress": 45 + int(30 * i / len(github_artifacts))
                })
                
                try:
                    spawn_agent_container(job_id, repo_url, config, emit_event=emit_event)
                except Exception as e:
                    emit_event(job_id, {
                        "step": "agent_error",
                        "message": f"Agent failed for {repo_url}: {str(e)}"
                    })
        
        emit_event(job_id, {
            "step": "stage_2_complete",
            "message": "Code execution complete",
            "progress": 75
        })
        
        # STAGE 3: Evaluation
        emit_event(job_id, {
            "step": "stage_3_starting",
            "message": "Stage 3: Evaluating Reproducibility...",
            "progress": 80
        })
        
        # Run evaluation in background thread
        threading.Thread(
            target=evaluate_reproducibility_aspects,
            args=(job_id, llm_provider),
            kwargs={"emit_event": emit_event},
            daemon=True
        ).start()
    
    except Exception as e:
        emit_event(job_id, {
            "step": "error",
            "message": f"Error: {str(e)}"
        })
        
        update_job_status(job_id, "error", str(e))


@jobs_bp.route("/upload", methods=["POST"])
@require_auth
def upload_pdf():
    """Upload PDF for analysis."""
    from services.llm_service import init_llm_provider
    
    user_id = session['user_id']
    
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
    
    if file_size > Config.MAX_PDF_SIZE:
        return jsonify({"error": "PDF too large (max 100MB)"}), 400
    
    # Create job
    job_id = str(uuid.uuid4())
    pdf_filename = f"{job_id}.pdf"
    pdf_path = Config.UPLOAD_FOLDER / pdf_filename
    
    file.save(pdf_path)
    
    # Extract page count and generate thumbnail
    num_pages = extract_page_count(str(pdf_path))
    thumbnail_path = generate_pdf_thumbnail(str(pdf_path), job_id, Config.THUMBNAILS_FOLDER)
    
    # Create job in database
    create_job(job_id, str(pdf_path), file.filename, user_id, thumbnail_path, num_pages)
    
    # Get configuration
    config = {
        "container": request.form.get("container", "python"),
        "model": request.form.get("model", "haiku"),
        "cpu_limit": int(request.form.get("cpu_limit", 4)),
        "memory_limit": int(request.form.get("memory_limit", 2048)),
        "runtime_limit": int(request.form.get("runtime_limit", 30)),
        "max_iterations": int(request.form.get("max_iterations", 3)),
        "storage_limit": int(request.form.get("storage_limit", 10))
    }
    
    # Start analysis thread
    try:
        llm_provider = init_llm_provider()
        thread = threading.Thread(
            target=analyze_paper_background,
            args=(job_id, str(pdf_path), config, llm_provider),
            daemon=True
        )
        thread.start()
    except Exception as e:
        update_job_status(job_id, "error", str(e))
    
    return jsonify({
        "job_id": job_id,
        "message": "Paper uploaded successfully. Analysis starting..."
    }), 202


@jobs_bp.route("/events/<job_id>")
@require_auth
def events(job_id):
    """Server-Sent Events endpoint for streaming job progress."""
    import time
    
    user_id = session.get('user_id')
    
    # Verify user has access
    job = get_job(job_id)
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    def generate():
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


@jobs_bp.route("/")
def index():
    """Home page - redirect to login if not authenticated."""
    if 'user_id' not in session:
        return redirect('/login')
    return render_template("index.html")


@jobs_bp.route("/history")
@require_auth
def history():
    """History page - browse past analyses."""
    return render_template("history.html")


@jobs_bp.route("/job/<job_id>")
@require_auth
def get_job_detail(job_id):
    """Get job status and report."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
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


@jobs_bp.route("/jobs")
@require_auth
def list_jobs_api():
    """List all jobs for current user."""
    user_id = session.get('user_id')
    jobs = get_user_jobs(user_id)
    return jsonify(jobs)


@jobs_bp.route("/api/job/<job_id>/full", methods=["GET"])
@require_auth
def get_job_full(job_id):
    """Get full job data including all details."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Fetch related data
    events_list = get_job_events(job_id)
    artifacts = get_job_artifacts(job_id)
    
    # Fetch paper analysis
    from services.analysis_service import get_paper_analysis
    paper_analysis = get_paper_analysis(job_id) or {}
    
    response = {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"] if job["progress"] is not None else 0.0,  # 0.0-1.0
        "pdf_filename": job["pdf_filename"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "report": json.loads(job["report"]) if job["report"] else {},
        "error_message": job["error_message"],
        "events": events_list,
        "artifacts": artifacts,
        "paper_analysis": paper_analysis
    }
    
    return jsonify(response)


@jobs_bp.route("/reports/<job_id>")
@require_auth
def detail_page(job_id):
    """Serve detail page for a job."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/results/<job_id>")
@require_auth
def results_page(job_id):
    """Serve results page for a job."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/job/<job_id>", methods=["DELETE"])
@require_auth
def delete_job_route(job_id):
    """Delete a job."""
    try:
        user_id = session.get('user_id')
        
        job = get_job(job_id)
        
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        if job["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        if delete_job(job_id):
            return jsonify({"ok": True, "message": "Job deleted"})
        else:
            return jsonify({"error": "Failed to delete job"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
