"""Jobs blueprint - page routes only. API endpoints moved to api.py."""

import threading
from flask import Blueprint, render_template, session, redirect, jsonify, request
from utils.decorators import require_auth
from services.job_service import get_job, get_user_jobs, delete_job
from services.event_dispatcher import EventDispatcher
from services.pipeline_orchestrator import PipelineOrchestrator
from models.events import JobEvent

jobs_bp = Blueprint('jobs', __name__)

# Event dispatcher (no longer uses event_queues - all data via /api/job/<id>/full)
_dispatcher = EventDispatcher()

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


@jobs_bp.route("/reports/<job_id>")
@require_auth
def detail_page(job_id):
    """Serve detail page for a job."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job or job.user_id != user_id:
        return redirect('/')
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/results/<job_id>")
@require_auth
def results_page(job_id):
    """Serve results page for a job."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job or job.user_id != user_id:
        return redirect('/')
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/jobs", methods=["GET"])
@require_auth
def list_jobs():
    """List all jobs for current user - returns JSON."""
    user_id = session.get('user_id')
    jobs = get_user_jobs(user_id)
    return jsonify(jobs)


@jobs_bp.route("/job/<job_id>", methods=["GET"])
@require_auth
def job_detail(job_id):
    """Get job detail page - returns HTML or 403."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    return render_template("detail.html", job_id=job_id)


@jobs_bp.route("/job/<job_id>", methods=["DELETE"])
@require_auth
def delete_job_endpoint(job_id):
    """Delete a job - returns JSON."""
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


@jobs_bp.route("/events/<job_id>", methods=["GET"])
@require_auth
def events_endpoint(job_id):
    """Server-Sent Events endpoint for job progress."""
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Return streaming response with events
    def generate():
        """Generate SSE events for job progress."""
        # Get events from dispatcher
        for event in _dispatcher.get_events(job_id):
            yield f"data: {event}\n\n"
    
    return generate(), 200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }
