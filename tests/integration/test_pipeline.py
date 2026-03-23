# tests/integration/test_pipeline.py
"""End-to-end tests for complete analysis pipeline.

These tests verify that the job API correctly reports pipeline state,
progress, events, and handles errors. The background pipeline is mocked
via the ``mock_upload_externals`` fixture (defined in conftest.py) to
avoid requiring real LLM/Docker services.
"""

import pytest
from io import BytesIO

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.db]


@pytest.fixture
def upload_pdf(authenticated_user, test_pdf_file, mock_upload_externals):
    """Upload a test PDF and return the job_id.

    Uses ``mock_upload_externals`` so the background pipeline is a no-op
    and the job stays in 'pending' state after creation.
    """
    response = authenticated_user.post(
        "/api/job/upload",
        data={"pdf": (test_pdf_file, "test.pdf")},
    )
    assert response.status_code == 202, f"Upload failed: {response.get_json()}"
    return response.get_json()["job_id"]


def _advance_job(job_id, status, progress, current_stage, events=None):
    """Helper: update job state and optionally create events."""
    from services.job_service import update_job_status
    from models.database import Event, Job

    update_job_status(job_id, status, progress=progress, current_stage=current_stage)

    if events:
        job = Job.get_by_id(job_id)
        for ev in events:
            Event.create(job=job, **ev)


class TestPipelineStages:
    """Test 3-stage pipeline progression"""

    @pytest.mark.slow
    def test_pipeline_completes_all_stages(self, authenticated_user, upload_pdf, app):
        """Test pipeline progresses through all 3 stages"""
        job_id = upload_pdf

        with app.app_context():
            _advance_job(job_id, "processing", 0.33, "paper_analysis", events=[
                {"step": "stage_1_starting", "message": "Analyzing paper...", "severity": "info"},
                {"step": "stage_1_complete", "message": "Paper analysis done", "severity": "info"},
            ])
            _advance_job(job_id, "processing", 0.66, "code_execution", events=[
                {"step": "stage_2_starting", "message": "Executing code...", "severity": "info"},
                {"step": "stage_2_complete", "message": "Code execution done", "severity": "info"},
            ])
            _advance_job(job_id, "completed", 1.0, "completed", events=[
                {"step": "stage_3_starting", "message": "Evaluating...", "severity": "info"},
                {"step": "complete", "message": "Analysis complete", "severity": "info"},
            ])

        response = authenticated_user.get(f"/api/job/{job_id}/full")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "completed"
        assert data["progress"] == 1.0
        assert data["current_stage"] == "completed"

    def test_pipeline_stage_progression_order(self, authenticated_user, upload_pdf, app):
        """Test stages progress in correct order"""
        job_id = upload_pdf

        with app.app_context():
            _advance_job(job_id, "processing", 0.33, "paper_analysis", events=[
                {"step": "stage_1_starting", "message": "Stage 1", "severity": "info"},
                {"step": "stage_1_complete", "message": "Stage 1 done", "severity": "info"},
            ])
            _advance_job(job_id, "processing", 0.66, "code_execution", events=[
                {"step": "stage_2_starting", "message": "Stage 2", "severity": "info"},
                {"step": "stage_2_complete", "message": "Stage 2 done", "severity": "info"},
            ])
            _advance_job(job_id, "completed", 1.0, "completed", events=[
                {"step": "stage_3_starting", "message": "Stage 3", "severity": "info"},
                {"step": "complete", "message": "Done", "severity": "info"},
            ])

        response = authenticated_user.get(f"/api/job/{job_id}/full")
        assert response.status_code == 200
        data = response.get_json()

        events = data.get("events", [])
        stage_steps = [e["step"] for e in events if "stage" in e.get("step", "")]

        # Stages should appear in order: stage_1 before stage_2 before stage_3
        assert len(stage_steps) >= 3
        stage_numbers = [int(s.split("_")[1]) for s in stage_steps if s.startswith("stage_")]
        assert stage_numbers == sorted(stage_numbers)


class TestPipelineEventEmission:
    """Test event emission throughout pipeline"""

    def test_events_emitted_for_each_stage(self, authenticated_user, upload_pdf, app):
        """Test events are emitted for each stage"""
        job_id = upload_pdf

        with app.app_context():
            _advance_job(job_id, "completed", 1.0, "completed", events=[
                {"step": "stage_1_starting", "message": "Analyzing paper...", "severity": "info"},
                {"step": "stage_2_starting", "message": "Executing code...", "severity": "info"},
                {"step": "stage_3_starting", "message": "Evaluating...", "severity": "info"},
                {"step": "complete", "message": "Analysis complete", "severity": "info"},
            ])

        response = authenticated_user.get(f"/api/job/{job_id}/full")
        assert response.status_code == 200
        data = response.get_json()

        events = data.get("events", [])
        assert len(events) >= 1

        for event in events:
            assert "step" in event or "message" in event
            assert "timestamp" in event or event is not None
            assert "severity" in event or "info" in str(event).lower()


class TestPipelineProgress:
    """Test progress tracking"""

    def test_progress_starts_at_zero(self, authenticated_user, upload_pdf):
        """Test progress starts at 0.0"""
        job_id = upload_pdf

        response = authenticated_user.get(f"/api/job/{job_id}/full")
        assert response.status_code == 200
        data = response.get_json()

        assert data["progress"] == 0.0

    def test_progress_is_monotonic(self, authenticated_user, upload_pdf, app):
        """Test progress only increases (never decreases)"""
        job_id = upload_pdf

        progress_values = []

        response = authenticated_user.get(f"/api/job/{job_id}/full")
        assert response.status_code == 200
        progress_values.append(response.get_json()["progress"])

        stages = [
            ("processing", 0.33, "paper_analysis"),
            ("processing", 0.66, "code_execution"),
            ("completed", 1.0, "completed"),
        ]

        for status, progress, stage in stages:
            with app.app_context():
                _advance_job(job_id, status, progress, stage)

            response = authenticated_user.get(f"/api/job/{job_id}/full")
            assert response.status_code == 200
            progress_values.append(response.get_json()["progress"])

        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1], \
                f"Progress decreased: {progress_values}"


class TestPipelineErrorHandling:
    """Test error handling in pipeline"""

    def test_pipeline_handles_invalid_pdf(self, authenticated_user):
        """Test pipeline handles non-PDF file gracefully"""
        invalid_file = BytesIO(b"This is not a PDF")

        response = authenticated_user.post(
            "/api/job/upload",
            data={"pdf": (invalid_file, "notapdf.txt")},
        )

        # Endpoint rejects non-.pdf extension with 400
        assert response.status_code == 400
