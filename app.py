"""
Paper Reproducibility Checker - Flask Backend

Analyzes scientific papers for reproducibility by extracting code artifacts
and running them in isolated Docker containers with an LLM agent.
"""

import os
from flask import Flask, render_template
from flask_apispec import FlaskApiSpec
from config import Config
from models.database import init_db as init_peewee_db
from services.auth_service import create_default_admin_user
from services.llm_service import init_llm_provider
from services.docker_service import init_docker
from blueprints.auth import auth_bp
from blueprints.admin import admin_bp
from blueprints.jobs import jobs_bp, emit_event
from blueprints.api import api_bp

# Export for backward compatibility with tests and other imports
DATABASE = Config.DATABASE


def create_app():
    """Create and configure Flask application."""
    
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize database (Peewee ORM)
    init_peewee_db(app.logger)
    create_default_admin_user(app.logger)
    
    # Initialize LLM provider
    try:
        llm_provider = init_llm_provider(app.logger)
    except Exception as e:
        app.logger.error(f"Failed to initialize LLM provider: {e}")
        raise
    
    # Initialize Docker
    if init_docker():
        Config.DOCKER_AVAILABLE = True
        app.logger.info("✓ Docker initialized successfully")
    else:
        Config.DOCKER_AVAILABLE = False
        app.logger.warning("✗ Docker not available - agent execution will fail")
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(api_bp)
    
    # Initialize API documentation (FlaskApiSpec)
    app.config.update({
        "APISPEC_TITLE": "Paper Reproducibility Checker API",
        "APISPEC_VERSION": "1.0.0",
        "OPENAPI_VERSION": "3.0.2",
        "APISPEC_SWAGGER_URL": "/swagger/",      # Raw OpenAPI JSON spec
        "APISPEC_SWAGGER_UI_URL": "/docs/",      # Interactive Swagger UI
        "API_TITLE": "Paper Reproducibility Checker",
        "API_VERSION": "v1",
    })
    
    docs = FlaskApiSpec(app)
    app.logger.info("✓ API documentation initialized: /docs/ and /swagger/")
    
    # PHASE 8: Filter OpenAPI spec - keep only /api/* routes and remove OPTIONS methods
    # Register all routes first, then filter to keep only /api/* endpoints
    docs.register_existing_resources()
    
    # Remove non-API routes and OPTIONS methods from the OpenAPI spec
    try:
        if hasattr(docs, 'spec') and hasattr(docs.spec, '_paths'):
            # Remove non-API routes (those NOT starting with /api/)
            all_paths = list(docs.spec._paths.keys())
            paths_to_remove = [path for path in all_paths if not path.startswith('/api/')]
            
            for path in paths_to_remove:
                del docs.spec._paths[path]
            
            # Remove OPTIONS methods from all remaining /api/* paths
            # (OPTIONS are CORS preflight requests, not user-facing API operations)
            for path_spec in docs.spec._paths.values():
                if 'options' in path_spec:
                    del path_spec['options']
            
            api_count = len(docs.spec._paths)
            app.logger.info(f"✓ Filtered OpenAPI spec: {api_count} /api/* routes documented, OPTIONS methods removed ({len(paths_to_remove)} non-API routes excluded)")
    except Exception as e:
        app.logger.error(f"Failed to filter OpenAPI spec: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
    
    # Configure security schemes for API documentation
    docs.spec.components.security_scheme("sessionAuth", {
        "type": "apiKey",
        "name": "session_id",
        "in": "cookie",
        "description": "Session-based authentication via cookies"
    })
    
    # Error handlers for proper JSON responses
    @app.errorhandler(422)
    def handle_validation_error(err):
        """
        Handle validation errors from @use_kwargs (Marshmallow validation).
        
        flask-apispec returns 422 with HTML by default.
        This handler converts it to JSON format for API clients.
        
        Example error response:
        {
          "error": "Validation failed",
          "messages": {
            "password": ["Missing data for required field."]
          }
        }
        """
        headers = err.data.get('headers', None)
        messages = err.data.get('messages', {})
        
        # Flatten nested messages structure if present
        # messages can be: {"json": {"field": [errors]}} or {"field": [errors]}
        if isinstance(messages, dict) and 'json' in messages:
            messages = messages['json']
        
        response = {
            "error": "Validation failed",
            "messages": messages
        }
        
        if headers:
            return response, 422, headers
        return response, 422
    
    # Security headers and cache control
    @app.after_request
    def set_security_headers(response):
        """Set security headers and cache control."""
        from flask import request
        
        # Static files - disable caching
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        # Security headers (all responses)
        # Prevent browsers from MIME-sniffing files
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking attacks
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Enable browser XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Strict transport security (HTTPS only in production)
        if Config.FLASK_ENV == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Referrer policy (don't leak referrer to external sites)
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    # Serve thumbnails
    @app.route("/uploads/thumbnails/<filename>")
    def serve_thumbnail(filename):
        """Serve thumbnail image files."""
        from flask import send_file, abort
        import re
        from pathlib import Path
        
        # Security: only allow thumbnail filenames
        if not (filename.endswith('.jpg') or filename.endswith('.png')):
            abort(404)
        
        thumbnail_path = Config.THUMBNAILS_FOLDER / filename
        
        if not thumbnail_path.exists():
            abort(404)
        
        # Verify UUID format
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png)$', filename):
            abort(404)
        
        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'
        return send_file(str(thumbnail_path), mimetype=mimetype)
    
    # Simple public pages
    @app.route("/about")
    def about():
        """About page."""
        return render_template("about.html")
    
    # Error handlers with content negotiation
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors with content negotiation."""
        from flask import jsonify, request
        
        # If request came from API (/api/*) or wants JSON, return JSON
        if request.path.startswith("/api") or 'application/json' in request.accept_mimetypes:
            return jsonify({"error": "Not found"}), 404
        
        # Otherwise, render HTML error page
        return render_template("404.html"), 404
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 errors (bad requests, bad JSON) with content negotiation."""
        from flask import jsonify, request
        
        # For now, always return JSON for 400 errors since they typically come from API calls
        # (invalid JSON, missing required fields, type validation errors)
        return jsonify({"error": "Bad request"}), 400
    
    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors with content negotiation."""
        from flask import jsonify, request
        
        app.logger.error(f"Server error: {error}")
        
        # If request came from API (/api/*) or wants JSON, return JSON
        if request.path.startswith("/api") or 'application/json' in request.accept_mimetypes:
            return jsonify({"error": "Internal server error"}), 500
        
        # Otherwise, render HTML error page
        return render_template("500.html"), 500
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    # Run development server
    app.run(host="0.0.0.0", port=5000, debug=True)
