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


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
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
    
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        user = get_user_by_username(username)
        
        if not user or not verify_password(password, user[1]):
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Check if user is active
        if not user[3]:  # is_active is index 3
            return jsonify({"error": "Account not activated yet"}), 403
        
        # Set session
        session['user_id'] = user[0]
        session['username'] = user[2]
        
        return jsonify({"message": "Login successful", "redirect": "/"}), 200
    
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
        
        email = user[3]  # email is index 3
        created_at = user[5]  # created_at is index 5
        
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
        
        password_hash = user[1] if len(user) > 1 else None
        if not password_hash or not verify_password(old_password, password_hash):
            return jsonify({"error": "Current password is incorrect"}), 400
        
        # Update password
        if not update_password(user_id, new_password):
            return jsonify({"error": "Failed to update password"}), 500
        
        return jsonify({"ok": True, "message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
