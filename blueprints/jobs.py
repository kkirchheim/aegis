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
from services.event_dispatcher import EventDispatcher
from services.pipeline_orchestrator import PipelineOrchestrator
from models.events import JobEvent
from utils.pdf_utils import extract_page_count, generate_pdf_thumbnail
from database import get_db

jobs_bp = Blueprint('jobs', __name__)

# Event queues for SSE
event_queues = {}
event_queues_lock = threading.Lock()

# Event dispatcher
_dispatcher = EventDispatcher(event_queues=event_queues, event_queues_lock=event_queues_lock)

# Pipeline orchestrator
_orchestrator = PipelineOrchestrator(dispatcher=_dispatcher)


def emit_event(job_id, event_dict):
    """Emit event to SSE clients and update job progress for milestone events.
    
    Args:
        job_id: Job ID
        event_dict: Dict with 'step', 'message' (optional), 'severity' (optional), etc.
    """
    # Convert dict to JobEvent and dispatch
    event = JobEvent(
        job_id=job_id,
        step=event_dict.get("step", "unknown"),
        message=event_dict.get("message"),
        severity=event_dict.get("severity", "info"),
        progress=event_dict.get("progress"),
        content=event_dict.get("content"),
    )
    _dispatcher.emit(event)


def analyze_paper_background(job_id, pdf_path, config, llm_provider):
    """Background job for paper analysis.
    
    Delegates to PipelineOrchestrator to run the 3-stage pipeline.
    """
    _orchestrator.run_analysis(job_id, pdf_path, config, llm_provider)


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
    
    # Pre-create queue BEFORE background thread starts
    # This ensures all events get captured from the start
    with event_queues_lock:
        event_queues[job_id] = []
    print(f"[{job_id}] Queue pre-created for new job")
    
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
def events(job_id):
    """Server-Sent Events endpoint for streaming job progress."""
    import time
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Verify user has access
    job = get_job(job_id)
    if not job or job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    def generate():
        # Get or create queue (pre-created at job upload time)
        with event_queues_lock:
            if job_id not in event_queues:
                event_queues[job_id] = []
            q = event_queues[job_id]
        print(f"[{job_id}] Using queue (exists: {len(q)} pending events)")
        
        # Then send all historical events from database
        from services.job_service import get_job_events
        try:
            print(f"[{job_id}] Loading historical events from DB...")
            historical_events = get_job_events(job_id)
            print(f"[{job_id}] Found {len(historical_events)} historical events")
            for event in historical_events:
                print(f"[{job_id}] Sending historical event: {event.get('step')}")
                yield f"data: {json.dumps(event)}\n\n"
                time.sleep(0.01)
        except Exception as e:
            print(f"[{job_id}] Error loading historical events: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            print(f"[{job_id}] Starting to listen for new events")
            sent_complete = False
            
            # Keep stream open indefinitely until job completes
            while not sent_complete:
                if q:
                    event = q.pop(0)
                    print(f"[{job_id}] Sending new event: {event.get('step')}")
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    if event.get("step") == "complete" or event.get("step") == "error":
                        sent_complete = True
                else:
                    time.sleep(0.1)
        
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
    
    if job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    response = {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at
    }
    
    if job.report:
        response["report"] = json.loads(job.report) if isinstance(job.report, str) else job.report
    
    if job.error_message:
        response["error"] = job.error_message
    
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
    
    if job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Fetch related data
    events_list = get_job_events(job_id)
    artifacts = get_job_artifacts(job_id)
    
    # Fetch paper analysis
    from services.analysis_service import get_paper_analysis
    paper_analysis = get_paper_analysis(job_id) or {}
    
    # Get current_stage, default to pending if not set
    current_stage = job.current_stage or "pending"
    
    response = {
        "id": job.id,
        "status": job.status,
        "progress": job.progress if job.progress is not None else 0.0,  # 0.0-1.0
        "current_stage": current_stage,  # pipeline stage
        "pdf_filename": job.pdf_filename,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "report": json.loads(job.report) if job.report else {},
        "error_message": job.error_message,
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
    
    if not job or job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/results/<job_id>")
@require_auth
def results_page(job_id):
    """Serve results page for a job."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job or job.user_id != user_id:
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
        
        if job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        if delete_job(job_id):
            return jsonify({"ok": True, "message": "Job deleted"})
        else:
            return jsonify({"error": "Failed to delete job"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
