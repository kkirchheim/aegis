"""API blueprint - REST API endpoints."""

import json
import threading
import time
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from flask_apispec import doc, marshal_with, use_kwargs
from marshmallow import ValidationError, fields
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
    ChatMessageSchema, ChatMessageRequestSchema, ChatMessageResponseSchema, ChatHistorySchema,
    LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema, UserSchema,
    SuccessMessageSchema, EventSchema, HealthResponseSchema, CacheStatsResponseSchema,
    UploadJobResponseSchema,
    AgentThinkRequestSchema, AgentLogRequestSchema, AgentExecutionRequestSchema,
    AgentCompleteRequestSchema, AgentActionSchema, AgentResponseSchema,
    APIKeyCreateSchema, APIKeySchema, APIKeyGenerateSchema, APIKeyListSchema
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ============================================================================
# Authentication API Endpoints (Separated from page routes)
# ============================================================================
# OpenAPI Tags: "Authentication"

@api_bp.route("/auth/login", methods=["POST"])
@use_kwargs(LoginSchema, location="json")
@marshal_with(SessionSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Authentication"],
    description="Authenticate a user with username and password",
    responses={
        200: {"description": "Login successful", "schema": SessionSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized - invalid username or password", "schema": ErrorSchema()},
        403: {"description": "Forbidden - account not activated", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def api_login(username, password):
    """
    REST API endpoint for user login.
    
    Input is validated by LoginSchema (@use_kwargs):
    - username: 3-50 chars, required
    - password: 8-100 chars, required
    
    Returns:
    - 200: {"message": "Login successful", "redirect": "/"}
    - 401: {"error": "Invalid username or password"}
    - 403: {"error": "Account not activated yet"}
    - 400: {"error": "..."}
    - 500: {"error": "..."}
    """
    from services.auth_service import get_user_by_username, verify_password
    
    try:
        user = get_user_by_username(username)
        
        if not user or not verify_password(password, user.password_hash):
            return {"error": "Invalid username or password"}, 401
        
        # Check if user is active
        if not user.is_active:
            return {"error": "Account not activated yet"}, 403
        
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        
        # Return dict only (no tuple) for 200 - @marshal_with handles it
        return {"message": "Login successful", "redirect": "/"}
    
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/auth/register", methods=["POST"])
@use_kwargs(RegisterSchema, location="json")
@marshal_with(SessionSchema, code=201)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=409)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Authentication"],
    description="Register a new user account",
    responses={
        201: {"description": "Account created successfully", "schema": SessionSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        409: {"description": "Conflict - username or email already exists", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def api_register(username, email, password, confirm_password):
    """
    REST API endpoint for user registration.
    
    Input validated by RegisterSchema (@use_kwargs):
    - username: 3-50 chars, required
    - email: valid email, required
    - password: 8-100 chars, required
    - confirm_password: must match password, required
    
    Returns:
    - 201: {"message": "Account created...", "redirect": "/login"}
    - 400: {"error": "..."}
    - 409: {"error": "Username or email already exists"}
    - 500: {"error": "Failed to create account"}
    """
    from services.auth_service import user_exists, create_user
    
    try:
        # @use_kwargs already validated all inputs
        # Check if user exists
        if user_exists(username, email):
            return {"error": "Username or email already exists"}, 409
        
        # Check password confirmation (Marshmallow validates format, we check match)
        if password != confirm_password:
            return {"error": "Passwords do not match"}, 400
        
        # Create user
        user_id = create_user(username, email, password)
        if not user_id:
            return {"error": "Failed to create account"}, 500
        
        # Return dict only (no tuple) for 201 - @marshal_with with code=201 handles it
        return (
            {
                "message": "Account created. Awaiting activation by admin.",
                "redirect": "/login"
            },
            201  # Explicitly set 201 status
        )
    
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/auth/change-password", methods=["POST"])
@require_auth
@use_kwargs(ChangePasswordSchema, location="json")
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Authentication"],
    description="Change the password for the authenticated user",
    security=[{"sessionAuth": []}],
    responses={
        204: {"description": "Password changed successfully"},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized - current password incorrect", "schema": ErrorSchema()},
        404: {"description": "User not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def api_change_password(old_password, new_password, confirm_password):
    """
    REST API endpoint for changing user password.
    
    Input validated by ChangePasswordSchema (@use_kwargs):
    - old_password: required
    - new_password: 8-100 chars, required
    - confirm_password: must match new_password, required
    
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
        
        # @use_kwargs already validated inputs
        # Check password confirmation (Marshmallow validates format, we check match)
        if new_password != confirm_password:
            return {"error": "New passwords don't match"}, 400
        
        # Get user and verify old password
        user = get_user_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        if not verify_password(old_password, user.password_hash):
            return {"error": "Current password is incorrect"}, 401
        
        # Update password
        if not update_password(user_id, new_password):
            return {"error": "Failed to update password"}, 500
        
        return "", 204
    except Exception as e:
        return {"error": str(e)}, 500


# ============================================================================
# API Key Management Endpoints
# ============================================================================
# OpenAPI Tags: "API Keys"

@api_bp.route("/keys", methods=["GET"])
@require_auth
@marshal_with(APIKeyListSchema, code=200)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["API Keys"],
    description="List all API keys for authenticated user (prefix only)",
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "List of API keys retrieved", "schema": APIKeyListSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def list_api_keys():
    """
    List all API keys for current user.
    
    Only shows key prefix (first 8 characters) and metadata.
    Full key cannot be retrieved after generation (save it securely).
    
    Returns:
    - 200: {"keys": [...], "total": N}
    - 500: {"error": "..."}
    """
    from models.api_key import APIKey
    
    try:
        user_id = session.get('user_id')
        keys = APIKey.select().where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        
        return {
            "keys": [
                {
                    "id": str(k.id),
                    "name": k.name,
                    "key_prefix": k.key_prefix,
                    "created_at": k.created_at,
                    "last_used_at": k.last_used_at,
                    "is_active": k.is_active
                }
                for k in keys
            ],
            "total": len(keys)
        }
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/keys", methods=["POST"])
@require_auth
@use_kwargs(APIKeyCreateSchema, location="json")
@marshal_with(APIKeyGenerateSchema, code=201)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["API Keys"],
    description="Generate a new API key for authenticated user",
    security=[{"sessionAuth": []}],
    responses={
        201: {"description": "API key generated successfully", "schema": APIKeyGenerateSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def create_api_key(name):
    """
    Generate a new API key for current user.
    
    Input validated by APIKeyCreateSchema (@use_kwargs):
    - name: str (1-100 chars), required
    
    ⚠️ IMPORTANT: The full key is shown ONLY ONCE.
    After this response, the key cannot be retrieved.
    
    Returns:
    - 201: {"key": "prc_sk_...", "id": "...", ...}
    - 400: {"error": "..."}
    - 500: {"error": "..."}
    """
    from models.api_key import APIKey
    from utils.api_key_utils import generate_api_key, hash_api_key
    from datetime import datetime
    
    try:
        user_id = session.get('user_id')
        
        # Generate API key
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        # Store in database
        db_key = APIKey.create(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        
        return (
            {
                "id": str(db_key.id),
                "name": name,
                "key": api_key,  # ⚠️ Full key shown only once!
                "key_prefix": key_prefix,
                "created_at": db_key.created_at
            },
            201
        )
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/keys/<key_id>", methods=["DELETE"])
@require_auth
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["API Keys"],
    description="Revoke (delete) an API key",
    security=[{"sessionAuth": []}],
    params={"key_id": {"description": "API Key ID", "in": "path"}},
    responses={
        204: {"description": "API key revoked successfully"},
        404: {"description": "API key not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def revoke_api_key(key_id):
    """
    Revoke (delete) an API key.
    
    Once revoked, the key cannot be used for authentication.
    
    Returns:
    - 204: No content (success)
    - 404: {"error": "API key not found"}
    - 500: {"error": "..."}
    """
    from models.api_key import APIKey
    
    try:
        user_id = session.get('user_id')
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        # Ensure user owns this key
        key = APIKey.get_or_none(APIKey.id == key_id)
        if not key:
            return {"error": "API key not found"}, 404
        
        # Compare user IDs (get the raw int ID from the ForeignKey)
        key_user_id = key.user_id_id if hasattr(key, 'user_id_id') else key.user_id.id
        if key_user_id != int(user_id):
            return {"error": "API key not found"}, 404
        
        # Delete the key
        key.delete_instance()
        
        return "", 204
    except Exception as e:
        return {"error": str(e)}, 500


# ============================================================================
# System Endpoints
# ============================================================================
# OpenAPI Tags: "System"

@api_bp.route("/health", methods=["GET"])
@doc(
    tags=["System"],
    description="Health check endpoint - returns system status",
    responses={
        200: {"description": "System is healthy", "schema": HealthResponseSchema()},
        503: {"description": "Service unavailable", "schema": HealthResponseSchema()}
    }
)
@marshal_with(HealthResponseSchema, code=200)
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
    return (response), status_code


# ============================================================================
# Cache Management API
# ============================================================================

@api_bp.route("/cache/stats", methods=["GET"])
@require_admin
@doc(
    tags=["System"],
    description="Get cache statistics (admin only)",
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "Cache statistics retrieved", "schema": CacheStatsResponseSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - admin access required", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
@marshal_with(CacheStatsResponseSchema, code=200)
def cache_stats():
    """Get cache statistics."""
    stats = get_cache_stats()
    return (stats)


@api_bp.route("/cache/clear", methods=["DELETE"])
@require_admin
@doc(
    tags=["System"],
    description="Clear all cached data (admin only)",
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "Cache cleared successfully", "schema": SuccessMessageSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - admin access required", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
@marshal_with(SuccessMessageSchema, code=200)
def cache_clear():
    """Clear all cached data."""
    try:
        success, deleted_count = clear_cache()
        if success:
            return ({
                "ok": True,
                "message": f"Cache cleared - deleted {deleted_count} PDF files"
            })
        else:
            return ({"error": "Failed to clear cache"}), 500
    except Exception as e:
        return ({"error": str(e)}), 500


# ============================================================================
# Chat API
# ============================================================================
# OpenAPI Tags: "Chat"

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
@use_kwargs(ChatMessageRequestSchema, location="json")
@marshal_with(SuccessMessageSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=422)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Chat"],
    description="Send a message to chat with paper analysis",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"description": "Message sent successfully", "schema": SuccessMessageSchema()},
        400: {"description": "Bad request - job analysis not complete", "schema": ErrorSchema()},
        422: {"description": "Unprocessable Entity - validation error", "schema": ErrorSchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def chat_with_paper(job_id, message):
    """Chat with paper analysis.
    
    Input validated by ChatMessageRequestSchema (@use_kwargs):
    - message: 1-5000 chars, required
    
    Returns:
    - 200: {"ok": True}
    - 400: {"error": "Job analysis not complete"}
    - 403: {"error": "Access denied"}
    - 404: {"error": "Job not found"}
    - 500: {"error": "..."}
    """
    from services.llm_service import init_llm_provider
    from blueprints.jobs import emit_event
    from repositories import PaperAnalysisRepository, ExecutionDetailsRepository, AspectEvaluationRepository
    
    user_id = session.get('user_id')
    user_message = message.strip()
    
    try:
        # Verify job exists and user owns it
        job = JobRepository.get(job_id)
        
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        if job.status not in ["completed", "processing"]:
            return {"error": "Job analysis not complete"}, 400
        
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
            return {"error": str(e)}, 500
        
        return {"ok": True}
    
    except Exception as e:
        return ({"error": str(e)}), 500


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
@marshal_with(ChatHistorySchema, code=200)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Chat"],
    description="Get chat history for a job",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"description": "Chat history retrieved", "schema": ChatHistorySchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def get_chat_history_endpoint(job_id):
    """Get chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        # Check if job exists first (404) before checking permissions (403)
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        try:
            chat_session = ChatSession.get(ChatSession.job == job_id)
            history = get_chat_history(chat_session.id, limit=100)
            return {
                "messages": history if history else [],
                "total": len(history) if history else 0
            }
        except ChatSession.DoesNotExist:
            return {
                "messages": [],
                "total": 0
            }
    
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>/chat/history", methods=["DELETE"])
@require_auth
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Chat"],
    description="Delete chat history for a job",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        204: {"description": "Chat history deleted successfully"},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def delete_chat_history_endpoint(job_id):
    """Delete chat history."""
    user_id = session.get('user_id')
    
    try:
        job = JobRepository.get(job_id)
        
        # Check if job exists first (404) before checking permissions (403)
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        try:
            chat_session = ChatSession.get(ChatSession.job == job_id)
            ChatRepository.clear_history(chat_session.id)
        except ChatSession.DoesNotExist:
            pass
        
        # Return 204 No Content for successful deletion
        return "", 204
    
    except Exception as e:
        return {"error": str(e)}, 500


# ============================================================================
# Agent API - Backend provides reasoning to Docker agent
# ============================================================================
# OpenAPI Tags: "Internal"

# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/think", methods=["POST"])
@use_kwargs(AgentThinkRequestSchema, location="json")
@marshal_with(AgentActionSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=422)
@marshal_with(ErrorSchema, code=500)
def agent_think(job_id, repo_state=None):
    """
    Agent calls this to ask for next action.
    
    Input validated by AgentThinkRequestSchema (@use_kwargs):
    - job_id: UUID string, required
    - repo_state: dict with discovered_files, combined_output, executed_commands, errors
    - Extra fields are ignored
    
    Security: Validates job_id exists before processing.
    Job must exist in database - agents cannot invent job IDs.
    
    Returns:
    - 200: {"action": "...", "target": "...", "reasoning": "..."}
    - 400: {"error": "..."}
    - 404: {"error": "Invalid job_id"}
    - 500: {"error": "..."}
    """
    from services.llm_service import init_llm_provider
    from config import Config
    
    repo_state = repo_state or {}
    
    # SECURITY: Validate that job_id actually exists in database
    # This prevents agents from making up job IDs or accessing arbitrary jobs
    try:
        from models.database import Job
        job = Job.get_by_id(job_id)
        if not job:
            return {"error": "Invalid job_id"}, 404
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"[{job_id}] Job validation failed: {str(e)}")
        return {"error": "Failed to validate job"}, 500
    
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
        
        return action
    
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"[{job_id}] Agent decision failed: {str(e)}")
        return {"error": str(e), "action": "done"}, 500


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/log", methods=["POST"])
@use_kwargs(AgentLogRequestSchema, location="json")
@marshal_with(AgentResponseSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=422)
@marshal_with(ErrorSchema, code=500)
def agent_log(job_id, message=None):
    """Agent logs progress.
    
    Input validated by AgentLogRequestSchema (@use_kwargs):
    - job_id: UUID string, required
    - message: progress message, optional (extra fields are ignored)
    
    Security: Validates job_id exists before accepting logs.
    
    Returns:
    - 200: {"ok": True}
    - 400: {"error": "..."}
    - 404: {"error": "Invalid job_id"}
    - 422: {"error": "..."} - Validation error (missing required field)
    - 500: {"error": "..."}
    """
    from blueprints.jobs import emit_event
    
    message = message or ""
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return {"error": "Invalid job_id"}, 404
    except Exception as e:
        return {"error": "Failed to validate job"}, 500
    
    emit_event(job_id, {
        "step": "agent_progress",
        "message": message
    })
    
    return {"ok": True}


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/execution", methods=["POST"])
@use_kwargs(AgentExecutionRequestSchema, location="json")
@marshal_with(AgentResponseSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=422)
@marshal_with(ErrorSchema, code=500)
def agent_execution(job_id, commands_run=None, stdout_combined=None, actual_results=None,
                   dependencies_used=None, errors_summary=None, discovered_files=None,
                   test_info=None, randomness_info=None):
    """
    Agent stores execution details.
    
    Input validated by AgentExecutionRequestSchema (@use_kwargs):
    - job_id: UUID string, required
    - commands_run, stdout_combined, actual_results, dependencies_used, etc.: optional fields
    - Extra fields are ignored
    
    Security: Validates job_id exists before storing execution details.
    
    Returns:
    - 200: {"ok": True}
    - 400: {"error": "..."}
    - 404: {"error": "Invalid job_id"}
    - 500: {"error": "..."}
    """
    from models.database import ExecutionDetails
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return {"error": "Invalid job_id"}, 404
    except Exception as e:
        return {"error": "Failed to validate job"}, 500
    
    try:
        ExecutionDetails.create(
            job_id=job_id,
            commands_run=commands_run or "",
            stdout_combined=stdout_combined or "",
            actual_results=json.dumps(actual_results or {}),
            dependencies_used=dependencies_used or "",
            errors_summary=errors_summary or "",
            discovered_files=json.dumps(discovered_files or []),
            test_info=test_info or "",
            randomness_info=randomness_info or ""
        )
        
        return {"ok": True}
    
    except Exception as e:
        return {"error": str(e)}, 500


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/complete", methods=["POST"])
@use_kwargs(AgentCompleteRequestSchema, location="json")
@marshal_with(AgentResponseSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=422)
@marshal_with(ErrorSchema, code=500)
def agent_complete(job_id, success=None, message=None):
    """
    Agent reports completion.
    
    Input validated by AgentCompleteRequestSchema (@use_kwargs):
    - job_id: UUID string, required
    - success: bool, whether analysis succeeded, optional
    - message: completion message, optional
    - Extra fields are ignored
    
    NOTE: Agent does NOT control job status. Only emits event.
    Pipeline orchestrator manages job lifecycle (pending -> processing -> completed).
    
    Security: Validates job_id exists before accepting completion.
    
    Returns:
    - 200: {"ok": True}
    - 400: {"error": "..."}
    - 404: {"error": "Invalid job_id"}
    - 500: {"error": "..."}
    """
    from blueprints.jobs import emit_event
    
    success = success or False
    message = message or "Analysis complete"
    
    # SECURITY: Validate that job_id actually exists
    try:
        job = JobRepository.get(job_id)
        if not job:
            return {"error": "Invalid job_id"}, 404
    except Exception as e:
        return {"error": "Failed to validate job"}, 500
    
    try:
        # Just emit event - don't update job status (pipeline orchestrator handles that)
        status_label = "success" if success else "failed"
        emit_event(job_id, {
            "step": "agent_finished",
            "message": f"Agent finished: {message}",
            "agent_status": status_label
        })
        
        return {"ok": True}
    
    except Exception as e:
        return {"error": str(e)}, 500


# INTERNAL: Called by agent container, not documented in OpenAPI
@api_bp.route("/agent/script_result", methods=["POST"])
@use_kwargs({
    "job_id": fields.Str(required=True),
    "script_hash": fields.Str(required=True),
    "exit_code": fields.Int(required=True),
    "stdout": fields.Str(required=False, missing=""),
    "stderr": fields.Str(required=False, missing=""),
    "duration_ms": fields.Int(required=False, missing=0),
}, location="json")
@marshal_with(AgentResponseSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
def agent_script_result(job_id, script_hash, exit_code, stdout, stderr, duration_ms):
    """
    Agent reports script execution result.
    
    Input: job_id, script_hash, exit_code, stdout, stderr, duration_ms
    Returns: {"ok": True}
    """
    from models.database import Job
    from models.execution_script import ExecutionScript, ExecutionScriptResult
    from blueprints.jobs import emit_event
    import uuid
    
    # Validate job exists
    try:
        job = Job.get_by_id(job_id)
    except:
        return {"error": "Invalid job_id"}, 404
    
    # Validate script exists
    try:
        script = ExecutionScript.get_by_id(script_hash)
    except:
        return {"error": "Invalid script_hash"}, 404
    
    try:
        # Store result
        result = ExecutionScriptResult.create(
            id=uuid.uuid4(),
            job=job,
            script_hash=script_hash,
            exit_code=exit_code,
            stdout=stdout[:5000] if stdout else "",  # Limit output size
            stderr=stderr[:5000] if stderr else "",
            duration_ms=duration_ms
        )
        
        # Emit event for live display
        emit_event(job_id, {
            'event': 'script_executed',
            'script_name': script.name,
            'script_hash': script_hash,
            'exit_code': exit_code,
            'stdout': stdout[:500] if stdout else '',
            'stderr': stderr[:200] if stderr else '',
            'duration_ms': duration_ms
        })
        
        return {"ok": True}
    
    except Exception as e:
        return {"error": str(e)}, 500


# ============================================================================
# Job Management API
# ============================================================================
# OpenAPI Tags: "Jobs"

@api_bp.route("/job/upload", methods=["POST"])
@marshal_with(UploadJobResponseSchema, code=202)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=413)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Jobs"],
    description="Upload a PDF paper for analysis",
    security=[{"sessionAuth": []}],
    responses={
        202: {"description": "PDF uploaded successfully, analysis starting", "schema": UploadJobResponseSchema()},
        400: {"description": "Bad request - no file or invalid file", "schema": ErrorSchema()},
        413: {"description": "Payload too large - PDF exceeds max size", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def upload_pdf():
    """Upload PDF for analysis."""
    from services.llm_service import init_llm_provider
    from blueprints.jobs import analyze_paper_background, emit_event
    from utils.decorators import get_current_user_id
    from utils.api_key_utils import verify_api_key, InvalidAPIKeyError
    import os
    import uuid
    from flask import current_app
    
    # Manual auth check - support both session cookie and API key
    user_id = None
    
    # Try session cookie first
    if 'user_id' in session:
        user_id = session['user_id']
        current_app.logger.info(f"[upload_pdf] Authenticated via session: user_id={user_id}")
    else:
        # Try API key from Authorization header
        auth_header = request.headers.get('Authorization', '')
        current_app.logger.info(f"[upload_pdf] No session, checking header: {auth_header[:20] if auth_header else 'empty'}...")
        
        if auth_header.startswith('ApiKey '):
            api_key = auth_header[7:]  # Remove "ApiKey " prefix
            current_app.logger.info(f"[upload_pdf] Found ApiKey header: {api_key[:20]}...")
            try:
                user_id = verify_api_key(api_key)
                current_app.logger.info(f"[upload_pdf] API key verified: user_id={user_id}")
            except (InvalidAPIKeyError, Exception) as e:
                current_app.logger.error(f"[upload_pdf] API key verification failed: {str(e)}")
                pass  # Invalid key, treat as unauthorized
        else:
            current_app.logger.info(f"[upload_pdf] No ApiKey header found")
    
    if not user_id:
        current_app.logger.warning("[upload_pdf] Authentication failed - returning 401")
        return {"error": "Unauthorized"}, 401
    
    # Validate file
    if "pdf" not in request.files:
        return {"error": "No PDF file provided"}, 400
    
    file = request.files["pdf"]
    if file.filename == "":
        return {"error": "No file selected"}, 400
    
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "File must be a PDF"}, 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > Config.MAX_PDF_SIZE:
        return {"error": "PDF too large (max 100MB)"}, 413
    
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
    
    return (
        {
            "job_id": job_id,
            "status": "pending",
            "message": "Paper uploaded successfully. Analysis starting..."
        },
        202
    )  # Tuple required for 202 status code


@api_bp.route("/job", methods=["GET"])
@require_auth
@marshal_with(JobListSchema, code=200)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Jobs"],
    description="List all jobs for the authenticated user",
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "List of jobs retrieved successfully", "schema": JobListSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def list_jobs_api():
    """List all jobs for current user.
    
    Returns:
    - 200: {"jobs": [...], "total": N}
    - 500: {"error": "..."}
    """
    try:
        user_id = session.get('user_id')
        jobs = get_user_jobs(user_id)
        return {
            "jobs": jobs if jobs else [],
            "total": len(jobs) if jobs else 0
        }
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>", methods=["GET"])
@require_auth
@marshal_with(JobSchema, code=200)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Jobs"],
    description="Get job status and report",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"description": "Job details retrieved successfully", "schema": JobSchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def get_job_detail(job_id):
    """Get job status and report."""
    try:
        user_id = session.get('user_id')
        
        job = get_job(job_id)
        
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        response = {
            "id": job.id,
            "status": job.status,
            "progress": job.progress if job.progress is not None else 0.0,
            "current_stage": job.current_stage or "pending",
            "pdf_filename": job.pdf_filename,
            "thumbnail_path": job.thumbnail_path,
            "created_at": job.created_at,
            "completed_at": job.completed_at
        }
        
        if job.report:
            response["report"] = json.loads(job.report) if isinstance(job.report, str) else job.report
        
        if job.error_message:
            response["error"] = job.error_message
        
        return response
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>", methods=["DELETE"])
@require_auth
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Jobs"],
    description="Delete a job",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        204: {"description": "Job deleted successfully"},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def delete_job_route(job_id):
    """Delete a job."""
    try:
        user_id = session.get('user_id')
        
        job = get_job(job_id)
        
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        if delete_job(job_id):
            return "", 204
        else:
            return {"error": "Failed to delete job"}, 500
    
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>/full", methods=["GET"])
@marshal_with(JobDetailSchema, code=200)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    tags=["Jobs"],
    description="Get full job data including details, events, and analysis",
    security=[{"sessionAuth": []}, {"apiKey": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"description": "Full job data retrieved successfully", "schema": JobDetailSchema()},
        401: {"description": "Unauthorized - invalid API key or missing session", "schema": ErrorSchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def get_job_full(job_id):
    """Get full job data including all details."""
    from utils.api_key_utils import verify_api_key, InvalidAPIKeyError
    from flask import current_app
    
    try:
        # Manual auth check - support both session cookie and API key
        user_id = None
        
        # Try session cookie first
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            # Try API key from Authorization header
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('ApiKey '):
                api_key = auth_header[7:]  # Remove "ApiKey " prefix
                try:
                    user_id = verify_api_key(api_key)
                except (InvalidAPIKeyError, Exception):
                    pass
        
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        job = get_job(job_id)
        
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        # Fetch related data
        events_list = get_job_events(job_id)
        artifacts = get_job_artifacts(job_id)
        
        # Fetch paper analysis
        from services.analysis_service import get_paper_analysis
        paper_analysis = get_paper_analysis(job_id) or {}
        
        # Get current_stage, default to pending if not set
        current_stage = job.current_stage or "pending"
        
        # Enrich evaluation_results with aspect metadata
        evaluation_results = job.get_evaluation_results()
        if evaluation_results:
            from services.aspect_service import AspectService
            # Get all aspects for this user (to look up names/descriptions)
            all_aspects = AspectService.get_all_aspects_for_user(job.user_id)
            aspect_lookup = {str(a['id']): a for a in all_aspects}
            
            # Merge aspect metadata into results
            for aspect_id, result in evaluation_results.items():
                aspect_info = aspect_lookup.get(aspect_id)
                if aspect_info:
                    # Add name and description if not already present
                    if 'aspect_name' not in result:
                        result['aspect_name'] = aspect_info.get('name', 'Aspect')
                    if 'aspect_description' not in result:
                        result['aspect_description'] = aspect_info.get('prompt_to_use', '') or aspect_info.get('prompt', '')
        
        response = {
            "id": job.id,
            "status": job.status,
            "progress": job.progress if job.progress is not None else 0.0,  # 0.0-1.0
            "current_stage": current_stage,  # pipeline stage
            "pdf_filename": job.pdf_filename,
            "thumbnail_path": job.thumbnail_path,  # Thumbnail URL for UI display
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "report": json.loads(job.report) if job.report else {},
            "error_message": job.error_message,
            "events": events_list,
            "artifacts": artifacts,
            "paper_analysis": paper_analysis,
            "evaluation_results": evaluation_results  # Enriched with aspect metadata
        }
        
        return response
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>/events", methods=["GET"])
@require_auth
@doc(
    tags=["Jobs"],
    description="Get events for a job with optional timestamp filtering",
    security=[{"sessionAuth": []}],
    params={
        "job_id": {"description": "Job ID", "in": "path"},
        "since": {"description": "ISO format timestamp to get events after this time (optional)", "in": "query"}
    },
    responses={
        200: {"description": "Job events retrieved successfully", "schema": {"type": "object", "properties": {"events": {"type": "array"}, "completed": {"type": "boolean"}, "job_status": {"type": "string"}}}},
        400: {"description": "Bad request - invalid timestamp format", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
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
    
    try:
        user_id = session.get('user_id')
        
        job = get_job(job_id)
        
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
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
                return {"error": f"Invalid timestamp format: {str(e)}"}, 400
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
        
        return response
    except Exception as e:
        return {"error": str(e)}, 500


@api_bp.route("/job/<job_id>/script_results", methods=["GET"])
@require_auth
@doc(
    tags=["Jobs"],
    description="Get script execution results for a job",
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: {"description": "Script results retrieved successfully", "schema": {"type": "object"}},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - access denied", "schema": ErrorSchema()},
        404: {"description": "Job not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def get_script_results(job_id):
    """Get all script execution results for a job."""
    from models.database import Job
    from models.execution_script import ExecutionScript, ExecutionScriptResult
    
    try:
        user_id = session.get('user_id')
        
        # Validate job access
        job = get_job(job_id)
        if not job:
            return {"error": "Job not found"}, 404
        
        if job.user_id != user_id:
            return {"error": "Access denied"}, 403
        
        # Get all script results for this job
        results = (
            ExecutionScriptResult
            .select()
            .where(ExecutionScriptResult.job == job_id)
            .order_by(ExecutionScriptResult.created_at.asc())
        )
        
        results_data = []
        for r in results:
            try:
                script = ExecutionScript.get_by_id(r.script_hash)
                script_name = script.name
            except:
                script_name = "Unknown"
            
            results_data.append({
                "script_name": script_name,
                "script_hash": r.script_hash,
                "exit_code": r.exit_code,
                "stdout": r.stdout or '',
                "stderr": r.stderr or '',
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, 'isoformat') else str(r.created_at)
            })
        
        return {
            "results": results_data,
            "total": len(results_data)
        }
    
    except Exception as e:
        return {"error": str(e)}, 500
