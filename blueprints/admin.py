"""Admin blueprint - admin panel and user management."""

from flask import Blueprint, request, jsonify, render_template
from utils.decorators import require_admin
from database import get_db

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
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT id, username, email, is_active, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = c.fetchall()
        conn.close()
        
        return jsonify([dict(user) for user in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/activate", methods=["POST"])
@require_admin
def activate_user(user_id):
    """Activate a user - admin only."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Verify user exists
        c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "User not found"}), 404
        
        # Update user
        c.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True, "message": f"User {user['username']} activated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/deactivate", methods=["POST"])
@require_admin
def deactivate_user(user_id):
    """Deactivate a user - admin only."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Verify user exists
        c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deactivating admin
        if user['username'] == 'admin':
            conn.close()
            return jsonify({"error": "Cannot deactivate admin user"}), 400
        
        # Deactivate user
        c.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True, "message": f"User {user['username']} deactivated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    """Delete a user - admin only."""
    try:
        from pathlib import Path
        
        conn = get_db()
        c = conn.cursor()
        
        # Verify user exists
        c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "User not found"}), 404
        
        # Prevent deleting admin
        if user['username'] == 'admin':
            conn.close()
            return jsonify({"error": "Cannot delete admin user"}), 400
        
        # Delete user's jobs and related data
        c.execute("SELECT id FROM jobs WHERE user_id = ?", (user_id,))
        jobs = c.fetchall()
        
        for job in jobs:
            job_id = job[0]
            # Delete PDF file
            c.execute("SELECT pdf_path FROM jobs WHERE id = ?", (job_id,))
            pdf_row = c.fetchone()
            if pdf_row and pdf_row[0]:
                pdf_file = Path(pdf_row[0])
                if pdf_file.exists():
                    pdf_file.unlink()
            
            # Delete job data
            c.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM aspect_evaluations WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM execution_details WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM paper_analysis WHERE job_id = ?", (job_id,))
        
        # Delete user
        c.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True, "message": f"User {user['username']} deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
