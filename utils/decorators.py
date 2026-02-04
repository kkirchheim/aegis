"""Authentication and authorization decorators."""

from functools import wraps
from flask import session, jsonify


def require_auth(f):
    """Decorator to require authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Decorator to require admin authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        username = session.get('username')
        if username != 'admin':
            return jsonify({"error": "Forbidden - admin access required"}), 403
        
        return f(*args, **kwargs)
    return decorated_function
