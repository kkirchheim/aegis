"""Authentication and authorization decorators."""

from functools import wraps

from flask import g, jsonify, request, session

from models.database import User
from utils.api_key_utils import ExpiredAPIKeyError, InvalidAPIKeyError, verify_api_key


def require_auth(f):
    """
    Decorator to require authentication on routes.

    Verifies that user_id exists in session.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
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
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401

        # Second check: verify admin status in database
        # This prevents privilege escalation if session is hijacked
        try:
            user_id = session.get("user_id")

            # Verify user exists and is admin
            user = User.get_by_id(user_id)
            if not user or user.username != "admin":
                # User is not admin (or user doesn't exist)
                return jsonify({"error": "Forbidden - admin access required"}), 403

        except Exception:
            # If we can't verify, deny access (fail secure)
            return jsonify({"error": "Forbidden - admin access required"}), 403

        return f(*args, **kwargs)

    return decorated_function


def require_api_key(f):
    """
    Decorator to require API key authentication on routes.

    Validates API key from Authorization header: "Authorization: ApiKey <key>"
    Stores user_id in g.user_id for use in endpoint.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("ApiKey "):
            return jsonify({"error": "Unauthorized - missing or invalid Authorization header"}), 401

        api_key = auth_header[7:]  # Remove "ApiKey " prefix

        try:
            user_id = verify_api_key(api_key)
            g.user_id = user_id  # Store in Flask g object for use in endpoint
            return f(*args, **kwargs)

        except (InvalidAPIKeyError, ExpiredAPIKeyError):
            return jsonify({"error": "Unauthorized - invalid API key"}), 401
        except Exception:
            return jsonify({"error": "Unauthorized - authentication failed"}), 401

    return decorated_function


def require_auth_cookie_or_api_key(f):
    """
    Decorator to require authentication via cookie OR API key.

    Tries cookie first (Flask session), then API key from Authorization header.
    Stores user_id in session (cookie) or g.user_id (API key) for use in endpoint.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try cookie first
        if "user_id" in session:
            return f(*args, **kwargs)

        # Try API key
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("ApiKey "):
            api_key = auth_header[7:]  # Remove "ApiKey " prefix

            try:
                user_id = verify_api_key(api_key)
                g.user_id = user_id  # Store in Flask g object
                return f(*args, **kwargs)
            except (InvalidAPIKeyError, ExpiredAPIKeyError):
                return jsonify({"error": "Unauthorized - invalid API key"}), 401
            except Exception:
                return jsonify({"error": "Unauthorized - authentication failed"}), 401

        # Neither cookie nor API key provided
        return jsonify({"error": "Unauthorized"}), 401

    return decorated_function


def get_current_user_id():
    """
    Get the current authenticated user ID.

    Works with both session cookies and API keys.
    Returns the user_id from either session or g.user_id.

    Returns:
        int: User ID, or None if not authenticated
    """
    # Try session cookie first
    if "user_id" in session:
        return session["user_id"]

    # Try API key (stored in g by decorator)
    if hasattr(g, "user_id"):
        return g.user_id

    return None
