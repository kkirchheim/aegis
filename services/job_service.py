"""Job service - job creation, queries, user isolation."""

import json
from pathlib import Path
from repositories import JobRepository, EventRepository, ArtifactRepository
from models.database import Job


def create_job(job_id, pdf_path, pdf_filename, user_id, thumbnail_path=None, num_pages=None):
    """Create a new job in the database."""
    try:
        job = Job.create(
            id=job_id,
            user_id=user_id,
            pdf_path=str(pdf_path),
            pdf_filename=pdf_filename,
            status="pending",
            current_stage="pending",
            thumbnail_path=thumbnail_path,
            num_pages=num_pages
        )
        return True
    except Exception as e:
        return False


def get_job(job_id):
    """Get job by ID. Returns Peewee Job model."""
    return JobRepository.get(job_id)


def get_user_jobs(user_id):
    """Get all jobs for a user."""
    try:
        jobs = JobRepository.list_all(user_id=user_id, limit=50)
        # Convert to dict format for compatibility with frontend
        result = []
        for job in jobs:
            job_dict = {
                "id": job.id,
                "status": job.status,
                "pdf_filename": job.pdf_filename,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "thumbnail_path": job.thumbnail_path,
                "num_pages": job.num_pages,
            }
            result.append(job_dict)
        
        return result
    except Exception as e:
        return []


def update_job_status(job_id, status, error_message=None, progress=None, current_stage=None):
    """Update job status, progress, and optionally stage."""
    try:
        updates = {"status": status}
        if progress is not None:
            updates["progress"] = progress
        if current_stage is not None:
            updates["current_stage"] = current_stage
        if error_message:
            updates["error_message"] = error_message
        
        # Update using Peewee
        Job.update(updates).where(Job.id == job_id).execute()
        return True
    except Exception as e:
        return False


def update_job_completion(job_id, report=None):
    """Mark job as completed."""
    try:
        job = Job.get_by_id(job_id)
        job.status = "completed"
        job.current_stage = "completed"
        if report:
            job.set_report(report)
        
        from datetime import datetime
        job.completed_at = datetime.now()
        job.save()
        return True
    except Exception as e:
        return False


def delete_job(job_id):
    """Delete a job and all related data."""
    try:
        job = JobRepository.get(job_id)
        if job and job.pdf_path:
            pdf_file = Path(job.pdf_path)
            if pdf_file.exists():
                try:
                    pdf_file.unlink()
                except:
                    pass
        
        return JobRepository.delete(job_id)
    except Exception as e:
        return False


def store_artifacts(job_id, artifacts):
    """Store artifacts for a job."""
    try:
        for artifact in artifacts:
            ArtifactRepository.create(
                job_id=job_id,
                url=artifact.get("url"),
                artifact_type=artifact.get("type"),
                description=artifact.get("description")
            )
        return True
    except Exception as e:
        return False


def get_job_artifacts(job_id):
    """Get all artifacts for a job."""
    try:
        artifacts = ArtifactRepository.list_by_job(job_id)
        return [
            {
                "url": a.url,
                "artifact_type": a.artifact_type,
                "description": a.description
            }
            for a in artifacts
        ]
    except Exception as e:
        return []


def get_job_events(job_id):
    """Get all events for a job."""
    try:
        events = EventRepository.list_by_job(job_id)
        return [
            {
                "timestamp": e.timestamp,
                "step": e.step,
                "message": e.message,
                "severity": e.severity,
                "stage_duration_ms": getattr(e, 'stage_duration_ms', None)  # Include if present
            }
            for e in events
        ]
    except Exception as e:
        return []


def store_event(job_id, timestamp, step, message, severity="info"):
    """Store an event for a job."""
    return EventRepository.create(job_id, step, message, severity)
