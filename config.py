"""Application configuration."""

import os
import secrets
import logging
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logger for configuration
_logger = logging.getLogger(__name__)


def _get_or_generate_secret_key():
    """
    Get SECRET_KEY from environment or generate once if missing.
    
    In production, SECRET_KEY should be set explicitly in .env.
    In development, we generate once per process to prevent session loss on reload.
    """
    secret_key = os.getenv('SECRET_KEY')
    
    if secret_key:
        return secret_key
    
    # If not set, generate a new one
    # This is only suitable for development - production MUST set this explicitly
    generated_key = secrets.token_hex(32)
    
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        _logger.warning(
            "⚠️  SECRET_KEY not set in environment! Using auto-generated key. "
            "This will cause session loss on application restart. "
            "Set SECRET_KEY in .env immediately!"
        )
    
    return generated_key


class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = _get_or_generate_secret_key()
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv('SESSION_TIMEOUT_HOURS', '24')))
    
    # Flag to indicate if using auto-generated SECRET_KEY
    _USING_AUTO_GENERATED_SECRET_KEY = not os.getenv('SECRET_KEY')
    
    # Database
    DATABASE = os.getenv('DATABASE_PATH', 'reproducibility.db')
    
    # File uploads
    UPLOAD_FOLDER = Path("uploads")
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    THUMBNAILS_FOLDER = UPLOAD_FOLDER / "thumbnails"
    THUMBNAILS_FOLDER.mkdir(exist_ok=True)
    
    MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB
    
    # Backend URL
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
    
    # Agent configuration
    AGENT_CONTEXT_LIMIT = int(os.getenv("AGENT_CONTEXT_LIMIT", "10000"))
    
    # Caching
    ENABLE_CACHING = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
    
    # Docker
    DOCKER_AVAILABLE = False  # Will be set in app initialization
    DOCKER_NETWORK = os.getenv('DOCKER_NETWORK', 'workspace_traefik')
    DOCKER_BACKEND_URL = os.getenv('DOCKER_BACKEND_URL', 'http://paper-reproducibility:5000')


def get_config():
    """Get current application configuration."""
    return Config()
