"""Database initialization and management."""

import sqlite3
from config import Config


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(app_logger=None):
    """Initialize database schema."""
    conn = get_db()
    c = conn.cursor()
    
    # Create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migration: Add is_active column to existing users table
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 0")
        if app_logger:
            app_logger.info("Added is_active column to users table")
    except:
        pass  # Column already exists
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0.0,
            pdf_path TEXT NOT NULL,
            pdf_filename TEXT,
            report JSON,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            url TEXT,
            artifact_type TEXT,
            description TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            step TEXT,
            message TEXT,
            severity TEXT DEFAULT 'info',
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            pdf_hash TEXT,
            title TEXT,
            abstract TEXT,
            citations JSON,
            extracted_text TEXT,
            claimed_results JSON,
            methodology TEXT,
            dependencies TEXT,
            dataset_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    # Add missing columns if they don't exist (migration)
    for col_name in ["pdf_hash", "title", "abstract", "citations"]:
        try:
            c.execute(f"ALTER TABLE paper_analysis ADD COLUMN {col_name} TEXT")
            if app_logger:
                app_logger.info(f"Added {col_name} column to paper_analysis table")
        except:
            pass
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS execution_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            commands_run TEXT,
            stdout_combined TEXT,
            actual_results JSON,
            dependencies_used TEXT,
            errors_summary TEXT,
            discovered_files JSON,
            test_info TEXT,
            randomness_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    # Add missing columns to existing databases (backward compatibility)
    for col_name in ["discovered_files", "test_info", "randomness_info"]:
        try:
            c.execute(f"ALTER TABLE execution_details ADD COLUMN {col_name} TEXT")
        except:
            pass  # Column already exists
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS aspect_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            aspect_id TEXT NOT NULL,
            name TEXT,
            status TEXT,
            evidence TEXT,
            paper_supports BOOLEAN,
            code_supports BOOLEAN,
            conclusion TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    # Cache tables for pipeline stages
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_paper_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_hash TEXT UNIQUE NOT NULL,
            title TEXT,
            abstract TEXT,
            citations JSON,
            extracted_text TEXT,
            claimed_results JSON,
            methodology TEXT,
            dependencies TEXT,
            dataset_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add missing columns to cache_paper_analysis (migration)
    for col_name in ["title", "abstract", "citations"]:
        try:
            c.execute(f"ALTER TABLE cache_paper_analysis ADD COLUMN {col_name} TEXT")
            if app_logger:
                app_logger.info(f"Added {col_name} column to cache_paper_analysis table")
        except:
            pass
    
    # Add user_id to jobs table (migration for multi-user support)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER")
        if app_logger:
            app_logger.info("Added user_id column to jobs table")
    except:
        pass
    
    # Add thumbnail_path to jobs table (migration for PDF thumbnails)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN thumbnail_path TEXT")
        if app_logger:
            app_logger.info("Added thumbnail_path column to jobs table")
    except:
        pass
    
    # Add num_pages to jobs table (migration for PDF page count)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN num_pages INTEGER")
        if app_logger:
            app_logger.info("Added num_pages column to jobs table")
    except:
        pass
    
    # Add progress to jobs table (migration for progress tracking)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN progress REAL DEFAULT 0.0")
        if app_logger:
            app_logger.info("Added progress column to jobs table")
    except:
        pass
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_code_execution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            repo_hash TEXT NOT NULL,
            commands_run TEXT,
            stdout_combined TEXT,
            actual_results JSON,
            dependencies_used TEXT,
            errors_summary TEXT,
            discovered_files JSON,
            test_info TEXT,
            randomness_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_url, repo_hash)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache_evaluation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_hash TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            evaluations JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(paper_hash, code_hash)
        )
    """)
    
    # Chat tables for interactive paper Q&A
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
        )
    """)
    
    conn.commit()
    conn.close()
