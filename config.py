"""Application configuration."""

import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database
    DATABASE = "reproducibility.db"
    
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


def get_config():
    """Get current application configuration."""
    return Config()
