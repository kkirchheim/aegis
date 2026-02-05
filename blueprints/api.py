"""API blueprint - REST API endpoints."""

import json
import threading
import time
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from utils.decorators import require_auth, require_admin
from services.cache_service import get_cache_stats, clear_cache
from models.database import User, db, Job, ChatSession, ChatMessage
from repositories import JobRepository, ChatRepository
from config import Config
from services.job_service import (
    create_job, get_job, get_user_jobs, update_job_status, delete_job,
    store_artifacts, get_job_artifacts, get_job_events
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ============================================================================
# Authentication API Endpoints (Separated from page routes)
# ============================================================================

@api_bp.route("/auth/login", methods=["POST"])
def api_login():
    """
    REST API endpoint for user login.
    
    Request body (JSON):
    {
        "username": "user",
        "password": "password"
    }
    
    Returns:
    - 200: {"message": "Login successful", "redirect": "/"}
    - 401: {"error": "Invalid username or password"}
    - 403: {"error": "Account not activated yet"}
    - 400: {"error": "Username and password required"}
    """
    from services.auth_service import get_user_by_username, verify_password
    
    try:
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        user = get_user_by_username(username)
        
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({"error": "Account not activated yet"}), 403
        
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({"message": "Login successful", "redirect": "/"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auth/register", methods=["POST"])
def api_register():
    """
    REST API endpoint for user registration.
    
    Request body (JSON):
    {
        "username": "user",
        "email": "user@example.com",
        "password": "password",
        "confirm_password": "password"
    }
    
    Returns:
    - 201: {"message": "Account created...", "redirect": "/login"}
    - 400: {"error": "..."}
    - 500: {"error": "Failed to create account"}
    """
    from services.auth_service import user_exists, create_user
    from utils.validators import (
        validate_username, validate_email, validate_password, validate_passwords_match
    )
    
    try:
        data = request.json or {}
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        
        # Validate inputs
        valid, error = validate_username(username)
        if not valid:
            return jsonify({"error": error}), 400
        
        valid, error = validate_email(email)
        if not valid:
            return jsonify({"error": error}), 400
        
        valid, error = validate_password(password)
        if not valid:
            return jsonify({"error": error}), 400
        
        valid, error = validate_passwords_match(password, confirm_password)
        if not valid:
            return jsonify({"error": error}), 400
        
        # Check if user exists
        if user_exists(username, email):
            return jsonify({"error": "Username or email already exists"}), 400
        
        # Create user
        user_id = create_user(username, email, password)
        if not user_id:
            return jsonify({"error": "Failed to create account"}), 500
        
        return jsonify({
            "message": "Account created. Awaiting activation by admin.",
            "redirect": "/login"
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Health Check Endpoint
# ============================================================================

@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    
    Returns 200 if all critical services are healthy, 503 otherwise.
    
    Security: This endpoint is intentionally public and does NOT expose:
    - Detailed error messages or connection strings
    - System paths or configuration details
    - Internal service information that could aid attackers
    
    Returns minimal information: only the status code and overall health.
    """
    from services.docker_service import is_docker_available
    from services.llm_service import init_llm_provider
    
    # Internal checks (not exposed to client)
    database_healthy = False
    llm_healthy = False
    
    # Check database connection
    try:
        # Simple query to verify database works
        User.select().limit(1).exists()
        database_healthy = True
    except Exception as e:
        # Log error internally but don't expose to client
        import logging
        logging.error(f"Health check: Database connection failed: {str(e)}")
        database_healthy = False
    
    # Check LLM provider (optional)
    try:
        llm_provider = init_llm_provider()
        llm_healthy = True
    except Exception as e:
        # LLM provider is optional - not required for health
        llm_healthy = False
    
    # Determine overall health status
    # Critical services: flask and database only
    is_healthy = database_healthy
    
    # For production, return minimal information
    response = {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # In development/non-production, we can include more details
    # This helps with debugging but should be removed in production
    if Config.FLASK_ENV != 'production':
        response["checks"] = {
            "database": database_healthy,
            "docker": is_docker_available(),
            "llm_provider": llm_healthy
        }
    
    status_code = 200 if is_healthy else 503
    return jsonify(response), status_code


# ============================================================================
# Cache Management API
# ============================================================================

@api_bp.route("/cache/stats", methods=["GET"])
@require_admin
def cache_stats():
    """Get cache statistics."""
    stats = get_cache_stats()
    return jsonify(stats)


@api_bp.route("/cache/clear", methods=["DELETE"])
@require_admin
def cache_clear():
    """Clear all cached data."""
    try:
        success, deleted_count = clear_cache()
        if success:
            return jsonify({
                "ok": True,
                "message": f"Cache cleared - deleted {deleted_count} PDF files"
            })
        else:
            return jsonify({"error": "Failed to clear cache"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Chat API
# ============================================================================

def get_or_create_chat_session(job_id):
    """Get or create chat session."""
    try:
        session_id = ChatRepository.get_or_create_session(job_id)
        if session_id:
            return {"id": session_id, "job_id": job_id}
    except Exception as e:
        raise


def store_chat_message(session_id, role, content):
    """Store chat message."""
    try:
        ChatRepository.save_message(session_id, role, content)
    except Exception as e:
        pass


def get_chat_history(session_id, limit=20):
    """Get chat history."""
    try:
        messages = ChatRepository.get_history(session_id, limit=limit)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    except Exception as e:
        return []


@api_bp.route("/job/<job_id>/chat", methods=["POST"])
@require_auth
def chat_with_paper(job_id):
    """Chat with paper analysis."""
    from services.llm_service import init_llm_provider
    from blueprints.jobs import emit_event
    
    user_id = session.get('user_id')
    data = request.json
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        # Verify job exists and user owns it
        job = JobRepository.get(job_id)
        
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        if job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        if job.status not in ["completed", "processing"]:
            return jsonify({"error": "Job analysis not complete"}), 400
        
        # Get or create session
        session_obj = get_or_create_chat_session(job_id)
        store_chat_message(session_obj["id"], "user", user_message)
        
        # Build context
        history = get_chat_history(session_obj["id"], limit=10)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        
        # Start response thread
        try:
            llm_provider = init_llm_provider()
            thread = threading.Thread(
                target=_generate_chat_response,
                args=(job_id, session_obj["id"], messages, llm_provider, emit_event),
                daemon=True
            )
            thread.start()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        return jsonify({"ok": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _generate_chat_response(job_id, session_id, messages, llm_provider, emit_event):
    """Generate chat response in background."""
    try:
        full_response = ""
        for chunk in llm_provider.stream(
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        ):
            if not chunk:
                continue
            full_response += chunk
            emit_event(job_id, {
                "step": "chat_response",
                "content": chunk
            })
        
        if not full_response:
            emit_event(job_id, {
                "step": "chat_error",
                "message": "Error: Empty response from LLM"
            })
            return
        
        store_chat_message(session_id, "assistant", full_response)
        
        emit_event(job_id, {
            "step": "chat_complete",
            "message": "Response complete"
        })
    
    except Exception as e:
        emit_event(job_id, {
            "step": "chat_error",
            "message": f"Error: {str(e)}"
        })


@api_bp.route("/job/<job_id>/chat/history", methods=["GET"])
@require_auth
def get_chat_history_endpoint(job_id):
    """Get chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        if not job or job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        try:
            chat_session = ChatSession.get(ChatSession.job == job_id)
            history = get_chat_history(chat_session.id, limit=100)
            return jsonify(history)
        except ChatSession.DoesNotExist:
            return jsonify([])
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/job/<job_id>/chat/history", methods=["DELETE"])
@require_auth
def delete_chat_history_endpoint(job_id):
    """Delete chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        if not job or job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        try:
            chat_session = ChatSession.get(ChatSession.job == job_id)
            ChatRepository.clear_history(chat_session.id)
        except ChatSession.DoesNotExist:
            pass
        
        return jsonify({"ok": True, "message": "Chat history cleared"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Agent API - Backend provides reasoning to Docker agent
# ============================================================================

@api_bp.route("/agent/think", methods=["POST"])
def agent_think():
    """
    Agent calls this to ask for next action.
    
    Security: Validates job_id exists before processing.
    Job must exist in database - agents cannot invent job IDs.
    """
    from services.llm_service import init_llm_provider
    from config import Config
    
    data = request.json
    job_id = data.get("job_id")
    repo_state = data.get("repo_state", {})
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # SECURITY: Validate that job_id actually exists in database
    # This prevents agents from making up job IDs or accessing arbitrary jobs
    try:
        from models.database import Job
        job = Job.get_by_id(job_id)
        if not job:
            return jsonify({"error": "Invalid job_id"}), 404
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"[{job_id}] Job validation failed: {str(e)}")
        return jsonify({"error": "Failed to validate job"}), 500
    
    try:
        # Build prompt for Claude
        files_list = (repo_state.get("discovered_files") or [])[:15]
        combined_output = repo_state.get("combined_output", "") or ""
        output_summary = combined_output[:Config.AGENT_CONTEXT_LIMIT] if combined_output else "(none)"
        executed_commands = repo_state.get("executed_commands", [])
        errors = repo_state.get("errors") or []
        
        if executed_commands:
            commands_summary = "Command history:\n" + "\n".join(
                f"  {i+1}. {cmd[:100]}" for i, cmd in enumerate(executed_commands)
            )
        else:
            commands_summary = "No commands executed yet"
        
        error_section = "- No errors yet"
        if errors:
            error_lines = []
            for e in errors[-2:]:
                cmd = e.get('command', 'unknown')
                stderr = e.get('stderr', 'unknown')[:100]
                error_lines.append(f"  - {cmd}: {stderr}")
            error_section = "Recent errors:\n" + "\n".join(error_lines)
        
        prompt = f"""You are an agent inside a Docker container attempting to reproduce code.

GOAL: Clone repository, understand how to run it, and execute it successfully.

CURRENT STATE:
- Repository: {repo_state.get('repo_url', 'unknown')}
- Files: {files_list}
- Iteration: {repo_state.get('iteration', 0)}/15

{commands_summary}

OUTPUT (truncated):
{output_summary}

ERRORS:
{error_section}

INSTRUCTIONS:
1. List and read README.md or documentation
2. Look for setup.py, requirements.txt, environment.yml, Dockerfile
3. Install dependencies
4. Find and run the main script/application
5. Report success with check_success action

RESPONSE FORMAT (JSON only):
{{
  "action": "read_file" | "run_command" | "check_success" | "done",
  "target": "path or command",
  "reasoning": "why"
}}
"""
        
        llm_provider = init_llm_provider()
        response_text = llm_provider.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        
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
                action = {"action": "done", "reasoning": "Could not parse response"}
        
        return jsonify(action)
    
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"[{job_id}] Agent decision failed: {str(e)}")
        return jsonify({"error": str(e), "action": "done"}), 500


@api_bp.route("/agent/log", methods=["POST"])
def agent_log():
    """Agent logs progress.
    
    Security: Validates job_id exists before accepting logs.
    """
    from blueprints.jobs import emit_event
    
    data = request.json
    job_id = data.get("job_id")
    message = data.get("message", "")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return jsonify({"error": "Invalid job_id"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to validate job"}), 500
    
    emit_event(job_id, {
        "step": "agent_progress",
        "message": message
    })
    
    return jsonify({"ok": True})


@api_bp.route("/agent/execution", methods=["POST"])
def agent_execution():
    """
    Agent stores execution details.
    
    Security: Validates job_id exists before storing execution details.
    """
    from models.database import ExecutionDetails
    
    data = request.json
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return jsonify({"error": "Invalid job_id"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to validate job"}), 500
    
    try:
        ExecutionDetails.create(
            job_id=job_id,
            commands_run=data.get("commands_run", ""),
            stdout_combined=data.get("stdout_combined", ""),
            actual_results=json.dumps(data.get("actual_results", {})),
            dependencies_used=data.get("dependencies_used", ""),
            errors_summary=data.get("errors_summary", ""),
            discovered_files=json.dumps(data.get("discovered_files", [])),
            test_info=data.get("test_info", ""),
            randomness_info=data.get("randomness_info", "")
        )
        
        return jsonify({"ok": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/agent/complete", methods=["POST"])
def agent_complete():
    """
    Agent reports completion.
    
    NOTE: Agent does NOT control job status. Only emits event.
    Pipeline orchestrator manages job lifecycle (pending -> processing -> completed).
    
    Security: Validates job_id exists before accepting completion.
    """
    from blueprints.jobs import emit_event
    
    data = request.json
    job_id = data.get("job_id")
    success = data.get("success", False)
    message = data.get("message", "Analysis complete")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return jsonify({"error": "Invalid job_id"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to validate job"}), 500
    
    try:
        # Just emit event - don't update job status (pipeline orchestrator handles that)
        status_label = "success" if success else "failed"
        emit_event(job_id, {
            "step": "agent_finished",
            "message": f"Agent finished: {message}",
            "agent_status": status_label
        })
        
        return jsonify({"ok": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Job Management API
# ============================================================================

@api_bp.route("/job/upload", methods=["POST"])
def upload_pdf():
    """Upload PDF for analysis."""
    from services.llm_service import init_llm_provider
    from blueprints.jobs import analyze_paper_background, emit_event
    import os
    import uuid
    
    require_auth_decorator = require_auth  # Get the decorator function
    
    # Manual auth check since we can't use decorator on moved function
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
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
    from utils.pdf_utils import extract_page_count, generate_pdf_thumbnail
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


@api_bp.route("/job", methods=["GET"])
@require_auth
def list_jobs_api():
    """List all jobs for current user."""
    user_id = session.get('user_id')
    jobs = get_user_jobs(user_id)
    return jsonify(jobs)


@api_bp.route("/job/<job_id>", methods=["GET"])
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


@api_bp.route("/job/<job_id>", methods=["DELETE"])
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


@api_bp.route("/job/<job_id>/full", methods=["GET"])
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
    
    # Log raw database values before putting in response
    import sys
    print(f"[{job_id}] *** API /full READ FROM DB ***", file=sys.stderr)
    print(f"[{job_id}]     job.progress type={type(job.progress).__name__}, raw value={repr(job.progress)}", file=sys.stderr)
    print(f"[{job_id}]     job.status={job.status}, job.current_stage={job.current_stage}", file=sys.stderr)
    
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
    
    # Log response for debugging
    print(f"[{job_id}] *** API /full RESPONSE ***", file=sys.stderr)
    print(f"[{job_id}]     status={response['status']}, progress={response['progress']}, stage={response['current_stage']}, events={len(response['events'])}", file=sys.stderr)
    
    return jsonify(response)


# Polling endpoint removed - now use /api/job/<id>/full for all data
