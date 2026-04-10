"""Job service - job creation, queries, user isolation."""

from pathlib import Path

from models.database import Job
from repositories import ArtifactRepository, EventRepository, JobRepository


def create_job(job_id, pdf_path, pdf_filename, user_id, thumbnail_path=None, num_pages=None):
    """Create a new job in the database."""
    try:
        Job.create(
            id=job_id,
            user_id=user_id,
            pdf_path=str(pdf_path),
            pdf_filename=pdf_filename,
            status="pending",
            current_stage="pending",
            progress=0.0,  # Initialize progress to 0%
            thumbnail_path=thumbnail_path,
            num_pages=num_pages,
        )
        import sys

        print(f"[{job_id}] Job created with progress=0.0", file=sys.stderr)
        return True
    except Exception as e:
        import sys

        print(f"[{job_id}] Failed to create job: {e}", file=sys.stderr)
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
    except Exception:
        return []


def update_job_status(job_id, status, error_message=None, progress=None, current_stage=None):
    """Update job status, progress, and optionally stage.

    THIS IS THE ONLY PLACE WHERE JOB PROGRESS SHOULD BE UPDATED IN DATABASE.
    All other code paths should call this function, never update Job directly.
    """
    import sys

    try:
        # Build update dict
        updates = {Job.status: status}
        if progress is not None:
            updates[Job.progress] = progress
        if current_stage is not None:
            updates[Job.current_stage] = current_stage
        if error_message:
            updates[Job.error_message] = error_message

        # Log BEFORE updating database
        # print(f"[{job_id}] *** BEFORE DATABASE UPDATE ***", file=sys.stderr)
        # print(f"[{job_id}]     Incoming: status={status}, progress={progress}, stage={current_stage}", file=sys.stderr)

        # Get current values BEFORE update
        try:
            Job.get_by_id(job_id)
            # print(f"[{job_id}]     DB Before: progress={job_before.progress}, status={job_before.status}, stage={job_before.current_stage}", file=sys.stderr)
        except Exception:
            print(f"[{job_id}]     DB Before: (job not found)", file=sys.stderr)

        # Execute Peewee update with logging
        query = Job.update(updates).where(Job.id == job_id)
        # print(f"[{job_id}]     SQL: {query.sql()}", file=sys.stderr)

        result = query.execute()
        # print(f"[{job_id}]     ✓ Rows affected: {result}", file=sys.stderr)

        # If no rows were affected, the job doesn't exist - return early
        if result == 0:
            print(f"[{job_id}]     ⚠️  Job not found in database - cannot update", file=sys.stderr)
            return False

        # Get values AFTER update
        try:
            Job.get_by_id(job_id)
            # print(f"[{job_id}]     DB After: progress={job_after.progress}, status={job_after.status}, stage={job_after.current_stage}", file=sys.stderr)
            # print(f"[{job_id}]     ✓ CONFIRMED: progress type={type(job_after.progress).__name__}, value={job_after.progress}", file=sys.stderr)
        except Job.DoesNotExist:
            # This shouldn't happen since we just updated it, but handle gracefully
            print(f"[{job_id}]     ⚠️  Could not fetch updated job", file=sys.stderr)
            return False

        return True
    except Exception as e:
        print(f"[{job_id}] *** UPDATE FAILED ***", file=sys.stderr)
        print(f"[{job_id}]     Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
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
    except Exception:
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
                except Exception:
                    pass

        return JobRepository.delete(job_id)
    except Exception:
        return False


def store_artifacts(job_id, artifacts):
    """Store artifacts for a job."""
    try:
        for artifact in artifacts:
            ArtifactRepository.create(
                job_id=job_id,
                url=artifact.get("url"),
                artifact_type=artifact.get("type"),
                description=artifact.get("description"),
            )
        return True
    except Exception:
        return False


def get_job_artifacts(job_id):
    """Get all artifacts for a job."""
    try:
        artifacts = ArtifactRepository.list_by_job(job_id)
        return [{"url": a.url, "artifact_type": a.artifact_type, "description": a.description} for a in artifacts]
    except Exception:
        return []


def get_job_events(job_id):
    """Get all events for a job."""
    try:
        events = EventRepository.list_by_job(job_id)
        return [
            {
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
                "step": e.step,
                "message": e.message,
                "severity": e.severity,
                "stage_duration_ms": getattr(e, "stage_duration_ms", None),  # Include if present
            }
            for e in events
        ]
    except Exception:
        return []


def store_event(job_id, timestamp, step, message, severity="info"):
    """Store an event for a job."""
    return EventRepository.create(job_id, step, message, severity)
