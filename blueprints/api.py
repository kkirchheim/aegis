"""API blueprint - REST API endpoints."""

import json
import threading
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from utils.decorators import require_auth, require_admin
from services.cache_service import get_cache_stats, clear_cache
from database import get_db
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
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1")
        conn.close()
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

@api_bp.route("/job/<job_id>/chat", methods=["POST"])
@require_auth
def chat_with_paper(job_id):
    """Chat with paper analysis."""
    from services.llm_service import init_llm_provider
    from services.chat_service import ChatService
    from blueprints.jobs import emit_event
    
    user_id = session.get('user_id')
    data = request.json
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        # Verify access
        ok, error = ChatService.verify_access(job_id, user_id)
        if not ok:
            status_code = 403 if error == "Access denied" else (404 if "not found" in error else 400)
            return jsonify({"error": error}), status_code
        
        # Get or create session
        session_id = ChatService.get_or_create_session(job_id)
        ChatService.save_message(session_id, "user", user_message)
        
        # Build message history
        history = ChatService.get_history(session_id, limit=10)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        
        # Start response thread
        llm_provider = init_llm_provider()
        success = ChatService.start_response_thread(
            job_id, session_id, messages, llm_provider, emit_event
        )
        
        if not success:
            return jsonify({"error": "Failed to start chat response"}), 500
        
        return jsonify({"ok": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/job/<job_id>/chat/history", methods=["GET"])
@require_auth
def get_chat_history_endpoint(job_id):
    """Get chat history."""
    from services.chat_service import ChatService
    
    user_id = session.get('user_id')
    
    try:
        # Verify access
        ok, error = ChatService.verify_access(job_id, user_id)
        if not ok:
            status_code = 403 if error == "Access denied" else 404
            return jsonify({"error": error}), status_code
        
        # Get chat history
        session_id = ChatService.get_or_create_session(job_id)
        history = ChatService.get_history(session_id, limit=100)
        
        return jsonify(history)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/job/<job_id>/chat/history", methods=["DELETE"])
@require_auth
def delete_chat_history_endpoint(job_id):
    """Delete chat history."""
    from services.chat_service import ChatService
    
    user_id = session.get('user_id')
    
    try:
        # Verify access
        ok, error = ChatService.verify_access(job_id, user_id)
        if not ok:
            status_code = 403 if error == "Access denied" else 404
            return jsonify({"error": error}), status_code
        
        # Clear chat history
        session_id = ChatService.get_or_create_session(job_id)
        ChatService.clear_history(session_id)
        
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
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        conn.close()
        
        if not job:
            return jsonify({"error": "Invalid job_id"}), 404
    except Exception as e:
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
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        conn.close()
        
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
    data = request.json
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    # SECURITY: Validate that job_id actually exists
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        
        if not job:
            conn.close()
            return jsonify({"error": "Invalid job_id"}), 404
        conn.close()
    except Exception as e:
        return jsonify({"error": "Failed to validate job"}), 500
    
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
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        
        if not job:
            conn.close()
            return jsonify({"error": "Invalid job_id"}), 404
        conn.close()
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
