"""Admin blueprint - admin panel and user management."""

from flask import Blueprint, request, jsonify, render_template
from flask_apispec import doc, marshal_with, use_kwargs
from utils.decorators import require_admin
from models.database import User, Job
from repositories import UserRepository, JobRepository
from schemas import (
    UserListSchema, UserActionSchema, ErrorSchema, UpdateUserStatusSchema
)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route("/admin")
@require_admin
def admin_panel():
    """Admin panel page - list all users."""
    return render_template("admin.html")


@admin_bp.route("/api/admin/users", methods=["GET"])
@require_admin
@marshal_with(UserListSchema, code=200)
@marshal_with(ErrorSchema, code=500)
@doc(
    description="Get list of all users with their details",
    tags=["Admin"],
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "List of users retrieved successfully", "schema": UserListSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def get_all_users():
    """Get list of all users (JSON) - admin only."""
    try:
        users = list(User.select().order_by(User.created_at.desc()))
        
        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "is_active": u.is_active,
                    "created_at": u.created_at  # Let Marshmallow serialize datetime
                }
                for u in users
            ],
            "total": len(users)
        }
    except Exception as e:
        return {"error": str(e)}, 500


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@require_admin
@use_kwargs(UpdateUserStatusSchema, location="json")
@marshal_with(UserActionSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    description="Update user status (activate/deactivate)",
    tags=["Admin"],
    params={"user_id": {"description": "User ID", "in": "path"}},
    security=[{"sessionAuth": []}],
    responses={
        200: {"description": "User status updated successfully", "schema": UserActionSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        404: {"description": "User not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def update_user_status(user_id, is_active):
    """
    Update user status (is_active field) - admin only.
    
    Input validated by UpdateUserStatusSchema (@use_kwargs):
    - is_active: bool, required
    """
    try:
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Prevent deactivating admin
        if user.username == 'admin' and not is_active:
            return {"error": "Cannot deactivate admin user"}, 400
        
        # Update user status
        User.update(is_active=is_active).where(User.id == user_id).execute()
        
        action = 'activated' if is_active else 'deactivated'
        return {
            "ok": True,
            "message": f"User {user.username} {action} successfully"
        }
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating user: {e}")
        return {"error": "Failed to update user"}, 500


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=404)
@marshal_with(ErrorSchema, code=500)
@doc(
    description="Delete a user account and all associated data",
    tags=["Admin"],
    params={"user_id": {"description": "User ID", "in": "path"}},
    security=[{"sessionAuth": []}],
    responses={
        204: {"description": "User deleted successfully"},
        400: {"description": "Bad request - cannot delete admin", "schema": ErrorSchema()},
        404: {"description": "User not found", "schema": ErrorSchema()},
        500: {"description": "Internal server error", "schema": ErrorSchema()}
    }
)
def delete_user(user_id):
    """Delete a user - admin only."""
    try:
        from pathlib import Path
        from models.database import Event, Artifact, AspectEvaluation, ExecutionDetails, PaperAnalysis
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404
        
        # Prevent deleting admin
        if user.username == 'admin':
            return {"error": "Cannot delete admin user"}, 400
        
        # Delete user's jobs and related data
        user_jobs = list(Job.select().where(Job.user == user_id))
        
        for job in user_jobs:
            # Delete PDF file
            if job.pdf_path:
                pdf_file = Path(job.pdf_path)
                if pdf_file.exists():
                    pdf_file.unlink()
            
            # Delete job data (cascade deletes should handle this, but be explicit)
            Event.delete().where(Event.job == job.id).execute()
            Artifact.delete().where(Artifact.job == job.id).execute()
            AspectEvaluation.delete().where(AspectEvaluation.job == job.id).execute()
            ExecutionDetails.delete().where(ExecutionDetails.job == job.id).execute()
            PaperAnalysis.delete().where(PaperAnalysis.job == job.id).execute()
        
        # Delete user's jobs
        Job.delete().where(Job.user == user_id).execute()
        
        # Delete user
        User.delete_by_id(user_id)
        
        return "", 204  # 204 No Content for successful DELETE
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deleting user: {e}")
        return {"error": "Failed to delete user"}, 500
