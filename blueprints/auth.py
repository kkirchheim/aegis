"""Authentication blueprint - login, register, logout, profile, password change."""

from flask import Blueprint, request, jsonify, session, render_template, redirect
from services.auth_service import (
    hash_password, verify_password, get_user_by_username, get_user_by_id,
    user_exists, create_user, update_password
)
from utils.decorators import require_auth
from utils.validators import (
    validate_username, validate_email, validate_password, validate_passwords_match
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/register", methods=["GET"])
def register_page():
    """User registration page."""
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET"])
def login_page():
    """User login page."""
    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST", "GET"])
@require_auth
def logout():
    """User logout - clears session and redirects to login."""
    session.clear()
    return redirect("/login")


@auth_bp.route("/profile")
@require_auth
def profile():
    """User profile page with account information."""
    try:
        user_id = session.get('user_id')
        username = session.get('username')
        
        user = get_user_by_id(user_id)
        
        if not user:
            return redirect("/login")
        
        email = user.email
        created_at = user.created_at
        
        # Format created_at
        if created_at:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(created_at)
                created_at = dt.strftime('%B %d, %Y at %I:%M %p')
            except:
                pass
        
        return render_template("profile.html", 
                             username=username, 
                             email=email,
                             created_at=created_at)
    except Exception as e:
        return redirect("/")


@auth_bp.route("/change-password")
@require_auth
def change_password_page():
    """Change password page."""
    if 'user_id' not in session:
        return redirect("/login")
    return render_template("change-password.html")


@auth_bp.route("/api/change-password", methods=["POST"])
@require_auth
def api_change_password():
    """Change password endpoint."""
    try:
        user_id = session.get('user_id')
        data = request.get_json()
        
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
            return jsonify({"error": "Current password is incorrect"}), 400
        
        # Update password
        if not update_password(user_id, new_password):
            return jsonify({"error": "Failed to update password"}), 500
        
        return jsonify({"ok": True, "message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
