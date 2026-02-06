"""Tests for thumbnail inclusion in API responses."""

import pytest
import json
from uuid import uuid4
from models.database import User, Job
from services.job_service import get_user_jobs, get_job, create_job
from config import Config


@pytest.mark.db
class TestThumbnailAPI:
    """Tests that thumbnails are included in API responses."""
    
    def test_get_user_jobs_includes_thumbnail_path(self, app):
        """Test that thumbnail_path is included in user jobs list."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Create a job with thumbnail
            job_id = str(uuid4())
            thumbnail_path = "uploads/thumbnails/test.png"
            
            create_job(
                job_id=job_id,
                pdf_path="/tmp/test.pdf",
                pdf_filename="test.pdf",
                user_id=user.id,
                thumbnail_path=thumbnail_path,
                num_pages=10
            )
            
            # Get user jobs
            jobs = get_user_jobs(user.id)
            
            assert len(jobs) == 1
            job_data = jobs[0]
            
            # Verify thumbnail_path is present and correct
            assert "thumbnail_path" in job_data, "thumbnail_path not in get_user_jobs response"
            assert job_data["thumbnail_path"] == thumbnail_path, \
                f"Expected thumbnail_path '{thumbnail_path}', got '{job_data['thumbnail_path']}'"
            
            # Verify other expected fields
            assert job_data["id"] == job_id
            assert job_data["pdf_filename"] == "test.pdf"
            assert job_data["num_pages"] == 10
    
    def test_get_job_includes_thumbnail_path(self, app):
        """Test that thumbnail_path is included in get_job response."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Create a job with thumbnail
            job_id = str(uuid4())
            thumbnail_path = "uploads/thumbnails/another_test.png"
            
            create_job(
                job_id=job_id,
                pdf_path="/tmp/another_test.pdf",
                pdf_filename="another_test.pdf",
                user_id=user.id,
                thumbnail_path=thumbnail_path,
                num_pages=5
            )
            
            # Fetch the job directly
            job = get_job(job_id)
            
            assert job is not None
            assert job.thumbnail_path == thumbnail_path, \
                f"Expected thumbnail_path '{thumbnail_path}', got '{job.thumbnail_path}'"
    
    def test_job_without_thumbnail_returns_null(self, app):
        """Test that jobs without thumbnails return null for thumbnail_path."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Create a job WITHOUT thumbnail
            job_id = str(uuid4())
            
            create_job(
                job_id=job_id,
                pdf_path="/tmp/no_thumb.pdf",
                pdf_filename="no_thumb.pdf",
                user_id=user.id,
                thumbnail_path=None,  # Explicitly no thumbnail
                num_pages=3
            )
            
            # Get user jobs
            jobs = get_user_jobs(user.id)
            
            assert len(jobs) == 1
            job_data = jobs[0]
            
            # Verify thumbnail_path is present but None/null
            assert "thumbnail_path" in job_data, "thumbnail_path not in get_user_jobs response"
            assert job_data["thumbnail_path"] is None, \
                f"Expected None for missing thumbnail, got '{job_data['thumbnail_path']}'"
