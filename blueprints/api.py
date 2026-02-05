"""API blueprint - REST API endpoints."""

import json
import threading
import time
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from flask_apispec import doc, marshal_with, use_kwargs
from utils.decorators import require_auth, require_admin
from services.cache_service import get_cache_stats, clear_cache
from models.database import User, db, Job, ChatSession, ChatMessage
from repositories import JobRepository, ChatRepository, EventRepository
from config import Config
from services.job_service import (
    create_job, get_job, get_user_jobs, update_job_status, delete_job,
    store_artifacts, get_job_artifacts, get_job_events
)
from schemas import (
    JobSchema, JobListSchema, JobDetailSchema, ErrorSchema,
    ChatMessageSchema, ChatMessageResponseSchema, ChatHistorySchema,
    LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema, UserSchema,
    SuccessMessageSchema
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ============================================================================
# Authentication API Endpoints (Separated from page routes)
# ============================================================================

@api_bp.route("/auth/login", methods=["POST"])
@doc(tags=["Authentication"], 
     description="User login endpoint. Authenticates a user with username and password.",
     responses={200: SessionSchema(), 400: ErrorSchema(), 401: ErrorSchema()})
@use_kwargs(LoginSchema, location="json")
@marshal_with(SessionSchema, code=200)
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
        try:
            data = request.json or {}
        except Exception as e:
            return jsonify({"error": "Invalid JSON in request body"}), 400
        
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
@doc(tags=["Authentication"],
     description="User registration endpoint. Creates a new user account with username, email, and password.",
     responses={201: UserSchema(), 400: ErrorSchema(), 409: ErrorSchema()})
@use_kwargs(RegisterSchema, location="json")
@marshal_with(UserSchema, code=201)
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
        try:
            data = request.json or {}
        except Exception as e:
            return jsonify({"error": "Invalid JSON in request body"}), 400
        
        username = data.get("username", "")
        email = data.get("email", "").strip()
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        
        # Type validation - username and password should be strings
        if not isinstance(username, str):
            return jsonify({"error": "Username must be a string"}), 400
        if not isinstance(password, str):
            return jsonify({"error": "Password must be a string"}), 400
        if not isinstance(confirm_password, str):
            return jsonify({"error": "Confirm password must be a string"}), 400
        
        username = username.strip()
        
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
            return jsonify({"error": "Username or email already exists"}), 409
        
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


@api_bp.route("/auth/change-password", methods=["POST"])
@doc(tags=["Authentication"],
     description="Change user password endpoint. Requires session authentication. Validates old password and updates to new password.",
     security=[{"sessionAuth": []}],
     responses={204: None, 400: ErrorSchema, 401: ErrorSchema()})
@use_kwargs(ChangePasswordSchema, location="json")
@marshal_with(None, code=204)
@require_auth
def api_change_password():
    """
    REST API endpoint for changing user password.
    
    Request body (JSON):
    {
        "old_password": "current_password",
        "new_password": "new_password",
        "confirm_password": "new_password"
    }
    
    Returns:
    - 204: No Content (success)
    - 400: {"error": "..."}
    - 401: {"error": "Current password is incorrect"}
    - 404: {"error": "User not found"}
    - 500: {"error": "Failed to update password"}
    """
    from services.auth_service import get_user_by_id, verify_password, update_password
    
    try:
        user_id = session.get('user_id')
        data = request.get_json() or {}
        
        old_password = data.get("old_password", "").strip()
        new_password = data.get("new_password", "").strip()
        confirm_password = data.get("confirm_password", "").strip()
        
        # Validation
        if not old_password or not new_password or not confirm_password:
            return jsonify({"error": "All fields are required"}), 400
        
        if len(new_password) < 8:
            return jsonify({"error": "New password must be at least 8 characters"}), 400
        
        if new_password != confirm_password:
            return jsonify({"error": "New passwords don't match"}), 400
        
        # Get user and verify old password
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if not verify_password(old_password, user.password_hash):
            return jsonify({"error": "Current password is incorrect"}), 401
        
        # Update password
        if not update_password(user_id, new_password):
            return jsonify({"error": "Failed to update password"}), 500
        
        return "", 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Health Check Endpoint
# ============================================================================

@api_bp.route("/health", methods=["GET"])
@doc(description="Health check endpoint - verify system is operational", tags=["System"], responses={200: SuccessMessageSchema(), 500: ErrorSchema, 503: ErrorSchema()})
@marshal_with(SuccessMessageSchema(), code=200)
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
@doc(description="Get cache statistics", tags=["System"], security=[{"sessionAuth": []}], responses={200: "Cache statistics", 401: ErrorSchema, 403: ErrorSchema, 500: ErrorSchema()})
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
@doc(
    description="Chat with paper analysis",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"schema": ChatMessageResponseSchema()},
        400: {"schema": ErrorSchema()},
        401: {"schema": ErrorSchema()},
        403: {"schema": ErrorSchema()},
        404: {"schema": ErrorSchema()},
        500: {"schema": ErrorSchema()},
    }
)
@use_kwargs(ChatMessageSchema, location="json")
@marshal_with(ChatMessageResponseSchema, code=200)
def chat_with_paper(job_id):
    """Chat with paper analysis."""
    from services.llm_service import init_llm_provider
    from blueprints.jobs import emit_event
    from repositories import PaperAnalysisRepository, ExecutionDetailsRepository, AspectEvaluationRepository
    
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
        
        # FETCH PAPER AND ANALYSIS DATA
        paper_analysis = PaperAnalysisRepository.get(job_id)
        execution_details = ExecutionDetailsRepository.get(job_id)
        aspect_evaluations = AspectEvaluationRepository.list_by_job(job_id)
        
        # Get or create session
        session_obj = get_or_create_chat_session(job_id)
        store_chat_message(session_obj["id"], "user", user_message)
        
        # Build context
        history = get_chat_history(session_obj["id"], limit=10)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        
        # Start response thread with paper context
        try:
            llm_provider = init_llm_provider()
            thread = threading.Thread(
                target=_generate_chat_response,
                args=(
                    job_id, 
                    session_obj["id"], 
                    messages, 
                    llm_provider, 
                    emit_event,
                    paper_analysis,
                    execution_details,
                    aspect_evaluations
                ),
                daemon=True
            )
            thread.start()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        return jsonify({"ok": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _build_chat_system_prompt(paper_analysis, execution_details, aspect_evaluations):
    """Build system prompt with paper analysis and reproducibility context."""
    import json
    
    # Extract paper metadata
    paper_info = ""
    if paper_analysis:
        paper_info = f"""
PAPER INFORMATION:
═════════════════════════════════════════
Title: {paper_analysis.title or "Not extracted"}
Abstract: {(paper_analysis.abstract[:500] if paper_analysis.abstract else "Not available")}...

Methodology: {paper_analysis.methodology or "Not described"}

Dependencies/Libraries Mentioned: {paper_analysis.dependencies or "None mentioned"}

Dataset: {paper_analysis.dataset_description or "Not described"}
"""
    
    # Extract execution results
    execution_info = ""
    if execution_details:
        # Parse JSON fields safely
        actual_results = {}
        if execution_details.actual_results:
            try:
                actual_results = json.loads(execution_details.actual_results)
            except:
                pass
        
        discovered_files = []
        if execution_details.discovered_files:
            try:
                discovered_files = json.loads(execution_details.discovered_files)
            except:
                discovered_files = []
        
        execution_info = f"""
EXECUTION RESULTS:
═════════════════════════════════════════
Status: Successfully executed

Commands Run: {(execution_details.commands_run[:500] if execution_details.commands_run else "None recorded")}

Output (last 800 chars): {(execution_details.stdout_combined[-800:] if execution_details.stdout_combined else "No output")}

Files Discovered: {len(discovered_files)} files
Top files: {', '.join(discovered_files[:10])}

Actual Results: {(json.dumps(actual_results, indent=2) if actual_results else "No results recorded")}

Dependencies Used: {execution_details.dependencies_used or "Not logged"}

Errors Encountered: {execution_details.errors_summary or "No errors"}
"""
    
    # Extract reproducibility evaluations
    evaluations_info = ""
    if aspect_evaluations:
        eval_summary = []
        for eval_item in aspect_evaluations:
            status_emoji = "✓" if eval_item.status == "pass" else "✗" if eval_item.status == "fail" else "~"
            eval_summary.append(
                f"{status_emoji} {eval_item.name}: {eval_item.status}\n"
                f"  Evidence: {(eval_item.evidence[:200] if eval_item.evidence else 'N/A')}\n"
                f"  Paper supports: {eval_item.paper_supports}, Code supports: {eval_item.code_supports}"
            )
        
        evaluations_info = f"""
REPRODUCIBILITY ASSESSMENT:
═════════════════════════════════════════
{chr(10).join(eval_summary)}
"""
    
    # Build complete system prompt
    system_prompt = f"""You are an AI assistant specialized in analyzing scientific papers and their reproducibility.

You have access to detailed information about a research paper and the results of attempting to reproduce its code implementation.

Your role is to:
1. Answer questions about the paper's content, methodology, and findings
2. Explain the reproducibility assessment results
3. Provide insights on what worked, what didn't, and why
4. Suggest improvements or next steps for reproduction
5. Help interpret the gap between claimed and actual results

Always base your answers on the provided context. If information is not available, say so clearly.

{paper_info}

{execution_info}

{evaluations_info}

INSTRUCTIONS:
- Answer questions based on the paper and execution context provided above
- If asked about specific results or findings, cite the exact section
- Be honest about limitations and gaps in reproducibility
- Explain technical concepts when needed
- Suggest improvements or troubleshooting when appropriate
- IMPORTANT: Use PLAIN TEXT ONLY. Do NOT use markdown formatting (no bold, no italic, no headers, no code blocks, no bullet lists). Write responses as simple readable paragraphs with line breaks where appropriate.
"""
    
    return system_prompt


def _generate_chat_response(job_id, session_id, messages, llm_provider, emit_event, paper_analysis=None, execution_details=None, aspect_evaluations=None):
    """Generate chat response in background with paper context."""
    try:
        # BUILD SYSTEM PROMPT WITH PAPER CONTEXT
        system_prompt = _build_chat_system_prompt(
            paper_analysis,
            execution_details,
            aspect_evaluations
        )
        
        full_response = ""
        for chunk in llm_provider.stream(
            messages=messages,
            system=system_prompt,
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
@doc(
    description="Get chat history for a job",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"schema": ChatHistorySchema()},
        401: {"schema": ErrorSchema()},
        403: {"schema": ErrorSchema()},
        404: {"schema": ErrorSchema()},
        500: {"schema": ErrorSchema()},
    }
)
@marshal_with(ChatHistorySchema, code=200)
def get_chat_history_endpoint(job_id):
    """Get chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        # Check if job exists first (404) before checking permissions (403)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        if job.user_id != user_id:
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
@doc(
    description="Delete chat history for a job",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        204: {"description": "Chat history deleted successfully"},
        401: {"schema": ErrorSchema()},
        403: {"schema": ErrorSchema()},
        404: {"schema": ErrorSchema()},
        500: {"schema": ErrorSchema()},
    }
)
@marshal_with(None, code=204)
def delete_chat_history_endpoint(job_id):
    """Delete chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        # Check if job exists first (404) before checking permissions (403)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        if job.user_id != user_id:
            return jsonify({"error": "Access denied"}), 403
        
        try:
            chat_session = ChatSession.get(ChatSession.job == job_id)
            ChatRepository.clear_history(chat_session.id)
        except ChatSession.DoesNotExist:
            pass
        
        # Return 204 No Content for successful deletion
        return "", 204
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Agent API - Backend provides reasoning to Docker agent
# ============================================================================

# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/think", methods=["POST"])
@doc(description="Agent callback to request next action", hidden=True, tags=["Internal"])
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


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/log", methods=["POST"])
@doc(description="Agent callback to log progress", hidden=True, tags=["Internal"])
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


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/execution", methods=["POST"])
@doc(description="Agent callback to store execution details", hidden=True, tags=["Internal"])
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


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/complete", methods=["POST"])
@doc(description="Agent callback to report completion", hidden=True, tags=["Internal"])
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
@doc(description="Upload a PDF file for paper reproducibility analysis", tags=["Jobs"], security=[{"sessionAuth": []}], responses={202: "Job created and analysis started", 400: ErrorSchema, 401: ErrorSchema, 413: ErrorSchema, 500: ErrorSchema()})
@marshal_with(JobSchema, code=202)
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
        return jsonify({"error": "PDF too large (max 100MB)"}), 413
    
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
@doc(description="List all jobs for the current user", tags=["Jobs"], security=[{"sessionAuth": []}], responses={200: "List of jobs retrieved successfully", 401: ErrorSchema, 500: ErrorSchema()})
@marshal_with(JobListSchema, code=200)
def list_jobs_api():
    """List all jobs for current user."""
    user_id = session.get('user_id')
    jobs = get_user_jobs(user_id)
    return jsonify(jobs)


@api_bp.route("/job/<job_id>", methods=["GET"])
@require_auth
@doc(description="Get job status and report by job ID", tags=["Jobs"], security=[{"sessionAuth": []}], params={"job_id": {"description": "Unique identifier for the job", "in": "path", "type": "string", "required": True}}, responses={200: "Job details retrieved successfully", 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema()})
@marshal_with(JobDetailSchema, code=200)
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
@doc(description="Delete a job by job ID", tags=["Jobs"], security=[{"sessionAuth": []}], params={"job_id": {"description": "Unique identifier for the job", "in": "path", "type": "string", "required": True}}, responses={204: "Job deleted successfully", 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema()})
@marshal_with(None, code=204)
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
            return "", 204
        else:
            return jsonify({"error": "Failed to delete job"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/job/<job_id>/full", methods=["GET"])
@require_auth
@doc(description="Get complete job data including all details, events, artifacts, and analysis", tags=["Jobs"], security=[{"sessionAuth": []}], params={"job_id": {"description": "Unique identifier for the job", "in": "path", "type": "string", "required": True}}, responses={200: "Full job details retrieved successfully", 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema()})
@marshal_with(JobDetailSchema, code=200)
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


@api_bp.route("/job/<job_id>/events", methods=["GET"])
@require_auth
@doc(description="SSE-compatible endpoint for streaming job events with optional timestamp filtering", 
     tags=["Jobs"], 
     security=[{"sessionAuth": []}],
     params={"job_id": {"description": "Unique identifier for the job", "in": "path", "type": "string", "required": True},
             "since": {"description": "ISO format timestamp to get events after this time (optional)", "in": "query", "type": "string", "required": False}},
     responses={200: "Events retrieved successfully", 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema()})
def get_job_events_polling(job_id):
    """Get events for a job with optional timestamp filtering.
    
    Query parameters:
    - since: ISO format timestamp to get events after this time (optional)
    
    Returns JSON with:
    - events: List of events (max 500)
    - completed: Boolean indicating if job is completed
    - job_status: Current job status string
    """
    from datetime import timezone
    
    user_id = session.get('user_id')
    
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job.user_id != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Get all events for the job
    all_events = EventRepository.list_by_job(job_id)
    
    # Handle 'since' parameter for filtering
    since_param = request.args.get('since')
    filtered_events = []
    
    if since_param:
        try:
            # Parse ISO format timestamp (e.g., "2024-01-01T12:00:00Z")
            if since_param.endswith('Z'):
                since_param = since_param[:-1] + '+00:00'
            since_time = datetime.fromisoformat(since_param)
            
            # Ensure since_time is timezone-aware (UTC)
            if since_time.tzinfo is None:
                since_time = since_time.replace(tzinfo=timezone.utc)
            
            # Filter events by timestamp
            for event in all_events:
                event_time = event.timestamp
                
                # Ensure event_time is timezone-aware (UTC) for comparison
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                
                if event_time > since_time:
                    filtered_events.append(event)
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid timestamp format: {str(e)}"}), 400
    else:
        filtered_events = all_events
    
    # Enforce 500 event limit for safety
    filtered_events = filtered_events[:500]
    
    # Convert events to dictionary format
    events_data = []
    for event in filtered_events:
        event_dict = {
            "id": str(event.id),
            "job_id": str(event.job_id),
            "step": event.step,
            "message": event.message,
            "severity": event.severity,
            "timestamp": event.timestamp.isoformat() + 'Z' if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
            "stage_duration_ms": event.stage_duration_ms
        }
        events_data.append(event_dict)
    
    # Determine if job is completed
    completed = job.status in ["completed", "failed", "cancelled"]
    
    response = {
        "events": events_data,
        "completed": completed,
        "job_status": job.status
    }
    
    return jsonify(response)
