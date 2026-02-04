"""Job service - job creation, queries, user isolation."""

import json
from pathlib import Path
from repositories import JobRepository
from models import Job
from database import get_db


def create_job(job_id, pdf_path, pdf_filename, user_id, thumbnail_path=None, num_pages=None) -> bool:
    """Create a new job in the database."""
    # Use repository to create job
    success = JobRepository.create(job_id, str(pdf_path), user_id)
    
    # Update additional fields
    if success:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "UPDATE jobs SET pdf_filename = ?, thumbnail_path = ?, num_pages = ? WHERE id = ?",
                (pdf_filename, thumbnail_path, num_pages, job_id)
            )
            conn.commit()
            conn.close()
        except:
            pass
    
    return success


def get_job(job_id) -> Job:
    """Get job by ID."""
    return JobRepository.get(job_id)


def get_user_jobs(user_id):
    """Get all jobs for a user."""
    jobs = JobRepository.list_all(user_id=user_id, limit=50)
    
    # Fetch paper analysis for each job
    try:
        conn = get_db()
        c = conn.cursor()
        
        result = []
        for job in jobs:
            c.execute("SELECT title, abstract FROM paper_analysis WHERE job_id = ?", (job.id,))
            paper_row = c.fetchone()
            
            job_dict = job.to_dict()
            if paper_row:
                job_dict['title'] = paper_row['title']
                job_dict['abstract'] = paper_row['abstract']
            
            result.append(job_dict)
        
        conn.close()
        return result
    except:
        return [job.to_dict() for job in jobs]


def update_job_status(job_id, status, error_message=None, progress=None, current_stage=None) -> bool:
    """Update job status, progress, and optionally stage."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        updates = ["status = ?"]
        params = [status]
        
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        
        if current_stage is not None:
            updates.append("current_stage = ?")
            params.append(current_stage)
        
        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)
        
        params.append(job_id)
        query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
        c.execute(query, params)
        
        conn.commit()
        conn.close()
        return True
    except:
        return False


def update_job_completion(job_id, report=None) -> bool:
    """Mark job as completed."""
    try:
        conn = get_db()
        c = conn.cursor()
        if report:
            report_json = json.dumps(report) if not isinstance(report, str) else report
            c.execute(
                "UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP, report = ? WHERE id = ?",
                ("completed", report_json, job_id)
            )
        else:
            c.execute(
                "UPDATE jobs SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("completed", job_id)
            )
        conn.commit()
        conn.close()
        return True
    except:
        return False


def delete_job(job_id) -> bool:
    """Delete a job and all related data."""
    try:
        # Get PDF path first
        job = JobRepository.get(job_id)
        if job and job.pdf_path:
            pdf_file = Path(job.pdf_path)
            if pdf_file.exists():
                try:
                    pdf_file.unlink()
                except:
                    pass
        
        # Delete using repository
        return JobRepository.delete(job_id)
    except:
        return False


def store_artifacts(job_id, artifacts) -> bool:
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
    except:
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
    except:
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
    except:
        return []


def store_event(job_id, timestamp, step, message, severity="info") -> bool:
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
    except:
        return False
