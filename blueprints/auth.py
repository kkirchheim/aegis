"""Authentication blueprint - login, register, logout, profile, password change."""

from flask import Blueprint, request, jsonify, session, render_template, redirect
from flask_apispec import doc, marshal_with, use_kwargs
from services.auth_service import (
    hash_password, verify_password, get_user_by_username, get_user_by_id,
    user_exists, create_user, update_password
)
from utils.decorators import require_auth
from utils.validators import (
    validate_username, validate_email, validate_password, validate_passwords_match
)
from schemas.auth import (
    LoginSchema, RegisterSchema, ChangePasswordSchema, SessionSchema
)
from schemas.common import ErrorSchema
from schemas.admin import UserSchema

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
    """User logout - clears session and returns 204 No Content."""
    session.clear()
    return "", 204


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


@auth_bp.route("/change-password", methods=["POST"])
@require_auth
def change_password():
    """User change password - JSON-based endpoint."""
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
        
        data = request.get_json() or {}
        old_password = data.get("old_password", "")
        new_password = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")
        
        # Get user
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 401
        
        # Verify old password
        if not verify_password(old_password, user.password_hash):
            return jsonify({"error": "Current password is incorrect"}), 401
        
        # Validate new password
        valid, error = validate_password(new_password)
        if not valid:
            return jsonify({"error": error}), 400
        
        # Check password confirmation
        valid, error = validate_passwords_match(new_password, confirm_password)
        if not valid:
            return jsonify({"error": error}), 400
        
        # Update password
        if not update_password(user_id, new_password):
            return jsonify({"error": "Failed to update password"}), 500
        
        return jsonify({"message": "Password changed successfully"}), 204
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login_form():
    """User login - form-based endpoint."""
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
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


@auth_bp.route("/register", methods=["POST"])
def register_form():
    """User registration - form-based endpoint."""
    try:
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
