"""Admin blueprint - admin panel and user management."""

from flask import Blueprint, request, jsonify, render_template
from utils.decorators import require_admin
from models.database import User, Job
from repositories import UserRepository, JobRepository

admin_bp = Blueprint('admin', __name__)


@admin_bp.route("/admin")
@require_admin
def admin_panel():
    """Admin panel page - list all users."""
    return render_template("admin.html")


@admin_bp.route("/api/admin/users", methods=["GET"])
@require_admin
def get_all_users():
    """Get list of all users (JSON) - admin only."""
    try:
        users = list(User.select().order_by(User.created_at.desc()))
        
        return jsonify([
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@require_admin
def update_user_status(user_id):
    """Update user status (is_active field) - admin only."""
    try:
        from flask import current_app
        
        data = request.json or {}
        is_active = data.get("is_active")
        
        if is_active is None:
            return jsonify({"error": "is_active field required"}), 400
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deactivating admin
        if user.username == 'admin' and not is_active:
            return jsonify({"error": "Cannot deactivate admin user"}), 400
        
        # Update user status
        User.update(is_active=is_active).where(User.id == user_id).execute()
        
        action = 'activated' if is_active else 'deactivated'
        return jsonify({
            "ok": True,
            "message": f"User {user.username} {action} successfully"
        }), 200
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating user: {e}")
        return jsonify({"error": "Failed to update user"}), 500


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """Delete a user - admin only."""
    try:
        from pathlib import Path
        from models.database import Event, Artifact, AspectEvaluation, ExecutionDetails, PaperAnalysis
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deleting admin
        if user.username == 'admin':
            return jsonify({"error": "Cannot delete admin user"}), 400
        
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
        return jsonify({"error": "Failed to delete user"}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/activate", methods=["POST"])
@require_admin
def activate_user(user_id):
    """Activate a user - admin only."""
    try:
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Update user status
        User.update(is_active=True).where(User.id == user_id).execute()
        
        return jsonify({
            "ok": True,
            "message": f"User {user.username} activated successfully"
        }), 200
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error activating user: {e}")
        return jsonify({"error": "Failed to activate user"}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/deactivate", methods=["POST"])
@require_admin
def deactivate_user(user_id):
    """Deactivate a user - admin only."""
    try:
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deactivating admin
        if user.username == 'admin':
            return jsonify({"error": "Cannot deactivate admin user"}), 400
        
        # Update user status
        User.update(is_active=False).where(User.id == user_id).execute()
        
        return jsonify({
            "ok": True,
            "message": f"User {user.username} deactivated successfully"
        }), 200
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deactivating user: {e}")
        return jsonify({"error": "Failed to deactivate user"}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user_post(user_id):
    """Delete a user - admin only (POST version for compatibility)."""
    try:
        from pathlib import Path
        from models.database import Event, Artifact, AspectEvaluation, ExecutionDetails, PaperAnalysis
        from flask import current_app
        
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deleting admin
        if user.username == 'admin':
            return jsonify({"error": "Cannot delete admin user"}), 400
        
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
        
        return jsonify({"ok": True, "message": f"User {user.username} deleted successfully"}), 200
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deleting user: {e}")
        return jsonify({"error": "Failed to delete user"}), 500
