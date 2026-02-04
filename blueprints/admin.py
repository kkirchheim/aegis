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


@admin_bp.route("/api/admin/users/<int:user_id>/activate", methods=["POST"])
@require_admin
def activate_user(user_id):
    """Activate a user - admin only."""
    try:
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Update user
        User.update(is_active=True).where(User.id == user_id).execute()
        
        return jsonify({"ok": True, "message": f"User {user.username} activated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/deactivate", methods=["POST"])
@require_admin
def deactivate_user(user_id):
    """Deactivate a user - admin only."""
    try:
        # Verify user exists
        user = UserRepository.get_by_id(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deactivating admin
        if user.username == 'admin':
            return jsonify({"error": "Cannot deactivate admin user"}), 400
        
        # Deactivate user
        User.update(is_active=False).where(User.id == user_id).execute()
        
        return jsonify({"ok": True, "message": f"User {user.username} deactivated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    """Delete a user - admin only."""
    try:
        from pathlib import Path
        from models.database import Event, Artifact, AspectEvaluation, ExecutionDetails, PaperAnalysis
        
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
        
        return jsonify({"ok": True, "message": f"User {user.username} deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
