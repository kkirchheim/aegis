"""Job service - job creation, queries, user isolation."""

import json
from pathlib import Path
from database import get_db


def create_job(job_id, pdf_path, pdf_filename, user_id, thumbnail_path=None, num_pages=None):
    """Create a new job in the database."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id, thumbnail_path, num_pages) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, "pending", str(pdf_path), pdf_filename, user_id, thumbnail_path, num_pages)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def get_job(job_id):
    """Get job by ID."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        conn.close()
        return job
    except Exception as e:
        return None


def get_user_jobs(user_id):
    """Get all jobs for a user."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT 
                j.id, j.status, j.pdf_filename, j.created_at, j.completed_at, j.thumbnail_path, j.num_pages,
                p.title, p.abstract
            FROM jobs j
            LEFT JOIN paper_analysis p ON j.id = p.job_id
            WHERE j.user_id = ?
            ORDER BY j.created_at DESC
            LIMIT 50
        """, (user_id,))
        jobs = c.fetchall()
        conn.close()
        return [dict(job) for job in jobs]
    except Exception as e:
        return []


def update_job_status(job_id, status, error_message=None, progress=None):
    """Update job status and optionally progress.
    
    Args:
        job_id: Job ID
        status: New status ('pending', 'processing', 'completed', 'failed')
        error_message: Optional error message if status='failed'
        progress: Optional progress (0.0 to 1.0)
    """
    try:
        conn = get_db()
        c = conn.cursor()
        
        if progress is not None:
            # Update status and progress
            if error_message:
                c.execute(
                    "UPDATE jobs SET status = ?, progress = ?, error_message = ? WHERE id = ?",
                    (status, progress, error_message, job_id)
                )
            else:
                c.execute(
                    "UPDATE jobs SET status = ?, progress = ? WHERE id = ?",
                    (status, progress, job_id)
                )
        else:
            # Update only status (backward compatible)
            if error_message:
                c.execute(
                    "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
                    (status, error_message, job_id)
                )
            else:
                c.execute(
                    "UPDATE jobs SET status = ? WHERE id = ?",
                    (status, job_id)
                )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def update_job_completion(job_id, report=None):
    """Mark job as completed."""
    try:
        conn = get_db()
        c = conn.cursor()
        if report:
            c.execute(
                "UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP, report = ? WHERE id = ?",
                ("completed", json.dumps(report) if not isinstance(report, str) else report, job_id)
            )
        else:
            c.execute(
                "UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("completed", job_id)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def delete_job(job_id):
    """Delete a job and all related data."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Get PDF path for deletion
        c.execute("SELECT pdf_path FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        
        if job and job["pdf_path"]:
            pdf_file = Path(job["pdf_path"])
            if pdf_file.exists():
                pdf_file.unlink()
        
        # Delete related data
        c.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
        c.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
        c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def store_artifacts(job_id, artifacts):
    """Store artifacts for a job."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        for artifact in artifacts:
            c.execute(
                "INSERT INTO artifacts (job_id, url, artifact_type, description) VALUES (?, ?, ?, ?)",
                (job_id, artifact.get("url"), artifact.get("type"), artifact.get("description"))
            )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False


def get_job_artifacts(job_id):
    """Get all artifacts for a job."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT url, artifact_type, description FROM artifacts WHERE job_id = ?", (job_id,))
        artifacts = c.fetchall()
        conn.close()
        return [dict(a) for a in artifacts]
    except Exception as e:
        return []


def get_job_events(job_id):
    """Get all events for a job."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT timestamp, step, message, severity FROM events WHERE job_id = ? ORDER BY timestamp ASC",
            (job_id,)
        )
        events = c.fetchall()
        conn.close()
        return [dict(e) for e in events]
    except Exception as e:
        return []


def store_event(job_id, timestamp, step, message, severity="info"):
    """Store an event for a job."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO events (job_id, timestamp, step, message, severity) VALUES (?, ?, ?, ?, ?)",
            (job_id, timestamp, step, message, severity)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False
