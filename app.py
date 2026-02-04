"""
Paper Reproducibility Checker - Flask Backend

Analyzes scientific papers for reproducibility by extracting code artifacts
and running them in isolated Docker containers with an LLM agent.
"""

import os
from flask import Flask, render_template
from config import Config
from database import init_db, get_db
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
    
    # Initialize database
    init_db(app.logger)
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
    
    # Static files - disable caching
    @app.after_request
    def set_cache_headers(response):
        """Disable caching for static files."""
        from flask import request
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
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
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        from flask import jsonify
        return jsonify({"error": "Not found"}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors."""
        from flask import jsonify
        app.logger.error(f"Server error: {error}")
        return jsonify({"error": "Internal server error"}), 500
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    # Run development server
    app.run(host="0.0.0.0", port=5000, debug=True)
