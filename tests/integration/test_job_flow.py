"""Integration tests for job API flow"""

from io import BytesIO

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]


class TestJobUpload:
    """Test PDF upload endpoint"""

    def test_upload_pdf_success(self, authenticated_user, test_pdf_file, mock_upload_externals):
        """Test uploading PDF successfully"""
        response = authenticated_user.post("/api/job/upload", data={"pdf": (test_pdf_file, "test.pdf")})

        assert response.status_code == 202  # Accepted
        data = response.get_json()
        assert "job_id" in data
        assert "status" in data
        assert "message" in data
        assert data["status"] == "pending"
        job_id = data["job_id"]
        assert len(job_id) > 0

    def test_upload_pdf_with_manual_artifact_urls(self, authenticated_user, test_pdf_file, mock_upload_externals):
        """Test uploading PDF with manual artifact URL overrides."""
        response = authenticated_user.post(
            "/api/job/upload",
            data={
                "pdf": (test_pdf_file, "test.pdf"),
                "manual_artifact_urls": "https://github.com/example/repo\nhttps://example.com/artifact",
            },
        )

        assert response.status_code == 202
        data = response.get_json()
        assert data["status"] == "pending"

    def test_upload_pdf_rejects_invalid_manual_artifact_url(
        self, authenticated_user, test_pdf_file, mock_upload_externals
    ):
        """Test upload validation rejects malformed manual artifact URLs."""
        response = authenticated_user.post(
            "/api/job/upload", data={"pdf": (test_pdf_file, "test.pdf"), "manual_artifact_urls": "not-a-url"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid artifact URL" in data["error"]

    def test_upload_pdf_unauthenticated(self, client, test_pdf_file):
        """Test upload requires authentication"""
        response = client.post("/api/job/upload", data={"pdf": (test_pdf_file, "test.pdf")})

        assert response.status_code == 401

    def test_upload_missing_file(self, authenticated_user):
        """Test upload without file"""
        response = authenticated_user.post("/api/job/upload", data={})

        assert response.status_code == 400

    def test_upload_too_large(self, authenticated_user):
        """Test upload exceeding size limit"""
        large_file = BytesIO(b"x" * (101 * 1024 * 1024))  # 101MB

        response = authenticated_user.post("/api/job/upload", data={"pdf": (large_file, "large.pdf")})

        assert response.status_code == 413  # Payload Too Large
        data = response.get_json()
        assert "error" in data


class TestJobList:
    """Test listing jobs"""

    def test_list_jobs_empty(self, authenticated_user):
        """Test listing jobs when none exist"""
        response = authenticated_user.get("/api/job")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) == 0
        assert data["total"] == 0

    def test_list_jobs_with_jobs(self, authenticated_user, test_job):
        """Test listing jobs when jobs exist"""
        response = authenticated_user.get("/api/job")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) >= 1
        assert data["total"] >= 1

    def test_list_jobs_unauthenticated(self, client):
        """Test listing requires authentication"""
        response = client.get("/api/job")

        assert response.status_code == 401

    def test_list_jobs_isolation(self, authenticated_user, other_user, mock_upload_externals, test_pdf_file):
        """Test users only see their own jobs"""
        # User 1 creates a job
        authenticated_user.post("/api/job/upload", data={"pdf": (test_pdf_file, "test.pdf")})

        # User 2 lists jobs (should see none)
        response = other_user.get("/api/job")
        data = response.get_json()

        assert "jobs" in data
        assert len(data["jobs"]) == 0  # Other user shouldn't see first user's jobs
        assert data["total"] == 0


class TestJobDetail:
    """Test getting job details"""

    def test_get_job_detail(self, authenticated_user, test_job):
        """Test getting job details"""
        response = authenticated_user.get(f"/api/job/{test_job['id']}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == test_job["id"]
        assert data["status"] in ["pending", "processing", "completed", "failed"]

    def test_get_job_full_data(self, authenticated_user, test_job):
        """Test getting complete job data (polling endpoint)"""
        response = authenticated_user.get(f"/api/job/{test_job['id']}/full")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == test_job["id"]
        assert "events" in data
        assert "artifacts" in data
        assert "progress" in data
        assert 0.0 <= data["progress"] <= 1.0

    def test_get_nonexistent_job(self, authenticated_user):
        """Test getting non-existent job"""
        response = authenticated_user.get("/api/job/nonexistent")

        assert response.status_code == 404

    def test_get_other_users_job(self, authenticated_user, other_user, test_job):
        """Test can't access other user's job"""
        response = other_user.get(f"/api/job/{test_job['id']}")

        assert response.status_code == 403


class TestJobDelete:
    """Test deleting jobs"""

    def test_delete_job_success(self, authenticated_user, test_job):
        """Test deleting a job"""
        job_id = test_job["id"]

        response = authenticated_user.delete(f"/api/job/{job_id}")

        assert response.status_code == 204  # No Content (standard for DELETE)

        # Verify job is deleted
        response = authenticated_user.get(f"/api/job/{job_id}")
        assert response.status_code == 404

    def test_delete_nonexistent_job(self, authenticated_user):
        """Test deleting non-existent job"""
        response = authenticated_user.delete("/api/job/nonexistent")

        assert response.status_code == 404

    def test_delete_other_users_job(self, authenticated_user, other_user, test_job):
        """Test can't delete other user's job"""
        response = other_user.delete(f"/api/job/{test_job['id']}")

        assert response.status_code == 403

    def test_delete_requires_auth(self, client, auth_test_job):
        """Test delete requires authentication"""
        response = client.delete(f"/api/job/{auth_test_job['id']}")

        assert response.status_code == 401


class TestJobPolling:
    """Test polling for job progress"""

    def test_polling_returns_progress(self, authenticated_user, test_job):
        """Test polling returns progress field"""
        response = authenticated_user.get(f"/api/job/{test_job['id']}/full")

        data = response.get_json()
        assert 0.0 <= data["progress"] <= 1.0

    def test_polling_returns_stage(self, authenticated_user, test_job):
        """Test polling returns current stage"""
        response = authenticated_user.get(f"/api/job/{test_job['id']}/full")

        assert response.status_code == 200
        data = response.get_json()
        assert "current_stage" in data
        assert data["current_stage"] in [
            "pending",
            "paper_analysis",
            "code_execution",
            "evaluation",
            "completed",
            "analysis",
        ]

    def test_polling_returns_events(self, authenticated_user, test_job):
        """Test polling returns event history"""
        response = authenticated_user.get(f"/api/job/{test_job['id']}/full")

        data = response.get_json()
        assert "events" in data
        assert isinstance(data["events"], list)
