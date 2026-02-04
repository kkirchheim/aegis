"""API blueprint - REST API endpoints."""

import json
import threading
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from utils.decorators import require_auth, require_admin
from services.cache_service import get_cache_stats, clear_cache
from models.database import User, db, Job, ChatSession, ChatMessage
from repositories import JobRepository, ChatRepository
from config import Config

api_bp = Blueprint('api', __name__, url_prefix='/api')


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
    
    Security: Validates job_id exists before accepting completion.
    """
    from blueprints.jobs import emit_event
    from services.job_service import update_job_status
    
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
        # Update job status based on success flag
        status = "completed" if success else "failed"
        progress = 1.0 if success else 0.0  # 100% if complete, 0% if failed
        current_stage = "completed" if success else "failed"
        
        result = update_job_status(job_id, status, progress=progress, current_stage=current_stage)
        
        emit_event(job_id, {
            "step": "agent_finished",
            "message": f"Agent finished: {message}",
            "status": status,
            "progress": 100
        })
        
        return jsonify({"ok": True, "status": status})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Polling Endpoint - Get Events Since Timestamp
# ============================================================================

@api_bp.route("/job/<job_id>/events", methods=["GET"])
@require_auth
def get_job_events_since(job_id):
    """
    Poll endpoint: Returns all events for a job since given timestamp.
    
    Query params:
    - since: ISO timestamp (e.g., 2026-02-05T00:00:00) - default: all events
    
    Returns: JSON list of events with fields:
    {
        "events": [
            {
                "id": "...",
                "job_id": "...",
                "step": "pdf_extracted",
                "message": "...",
                "severity": "info",
                "timestamp": "2026-02-05T00:01:23.456Z",
                "progress": 0.2,
                "duration_ms": 1234
            },
            ...
        ],
        "completed": true/false
    }
    """
    user_id = session.get('user_id')
    
    # Verify user owns this job
    try:
        job = JobRepository.get(job_id)
        if not job or job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
    except Exception as e:
        return jsonify({"error": "Invalid job"}), 404
    
    # Get 'since' parameter (ISO timestamp)
    since_str = request.args.get('since')
    since_dt = None
    
    if since_str:
        try:
            # Parse ISO format: 2026-02-05T00:01:23.456Z
            since_dt = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({"error": "Invalid timestamp format. Use ISO format."}), 400
    
    # Get events from database
    try:
        from models.database import Event
        query = Event.select().where(Event.job_id == job_id).order_by(Event.timestamp.asc())
        
        if since_dt:
            query = query.where(Event.timestamp > since_dt)
        
        events = query.limit(500)  # Safety limit
        
        events_list = [
            {
                "id": str(e.id),
                "job_id": str(e.job_id),
                "step": e.step,
                "message": e.message,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() + 'Z',
                "stage_duration_ms": e.stage_duration_ms
            }
            for e in events
        ]
        
        # Check if job is completed
        completed = job.status in ["completed", "failed", "error"]
        
        return jsonify({
            "events": events_list,
            "completed": completed,
            "job_status": job.status
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
