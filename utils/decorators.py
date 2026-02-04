"""Authentication and authorization decorators."""

from functools import wraps
from flask import session, jsonify


def require_auth(f):
    """
    Decorator to require authentication on routes.
    
    Verifies that user_id exists in session.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """
    Decorator to require admin authentication on routes.
    
    Security: Verifies admin status in database, not just session,
    to prevent privilege escalation if session is compromised.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check: user must be authenticated
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Second check: verify admin status in database
        # This prevents privilege escalation if session is hijacked
        try:
            from database import get_db
            
            user_id = session.get('user_id')
            username = session.get('username')
            
            # Verify user exists and is admin
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT username FROM users WHERE id = ? AND username = ?", (user_id, 'admin'))
            admin_user = c.fetchone()
            conn.close()
            
            if not admin_user:
                # User is not admin (or user doesn't exist)
                return jsonify({"error": "Forbidden - admin access required"}), 403
            
        except Exception as e:
            # If we can't verify, deny access (fail secure)
            return jsonify({"error": "Forbidden - admin access required"}), 403
        
        return f(*args, **kwargs)
    return decorated_function
