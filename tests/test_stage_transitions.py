"""Test stage transitions with mocked LLM responses."""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from blueprints.jobs import emit_event, analyze_paper_background
from services.job_service import update_job_status, create_job, get_job
from database import get_db
import uuid


class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def complete(self, **kwargs):
        """Return mock analysis results."""
        return json.dumps({
            "artifacts": [
                {"url": "https://github.com/test/repo", "type": "github_repo", "description": "Test repo"}
            ],
            "methodology": "Testing methodology",
            "claimed_results": "Testing results"
        })


@pytest.fixture
def mock_llm_provider():
    """Fixture for mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def test_job_id():
    """Create a test job ID."""
    return str(uuid.uuid4())


@pytest.fixture
def setup_test_job(test_job_id):
    """Setup a test job in the database."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO jobs (id, pdf_filename, pdf_path, status, user_id) 
           VALUES (?, ?, ?, ?, ?)""",
        (test_job_id, "test.pdf", "/tmp/test.pdf", "processing", 1)
    )
    conn.commit()
    conn.close()
    return test_job_id


def test_emit_event_stage_transitions(setup_test_job):
    """Test that emit_event correctly updates stage transitions."""
    job_id = setup_test_job
    events = []
    
    # Mock emit_event to capture events
    original_emit = emit_event
    
    def mock_emit(job_id, event):
        events.append((event["step"], event.get("message", "")))
        original_emit(job_id, event)
    
    # Test stage 1 transition
    mock_emit(job_id, {"step": "stage_1_starting", "message": "Stage 1 starting"})
    job = get_job(job_id)
    assert job["current_stage"] == "paper_analysis"
    
    # Test stage 1 complete transition
    mock_emit(job_id, {"step": "stage_1_complete", "message": "Stage 1 complete"})
    job = get_job(job_id)
    assert job["current_stage"] == "code_execution"
    
    # Test stage 2 starting
    mock_emit(job_id, {"step": "stage_2_starting", "message": "Stage 2 starting"})
    job = get_job(job_id)
    assert job["current_stage"] == "code_execution"
    
    # Test stage 2 complete
    mock_emit(job_id, {"step": "stage_2_complete", "message": "Stage 2 complete"})
    job = get_job(job_id)
    assert job["current_stage"] == "evaluation"
    
    # Test stage 3 starting
    mock_emit(job_id, {"step": "stage_3_starting", "message": "Stage 3 starting"})
    job = get_job(job_id)
    assert job["current_stage"] == "evaluation"
    
    # Test stage 3 complete - should still be evaluation
    mock_emit(job_id, {"step": "stage_3_complete", "message": "Stage 3 complete"})
    job = get_job(job_id)
    assert job["current_stage"] == "evaluation", "Should stay in evaluation after stage_3_complete"
    
    # Test final complete - should transition to completed
    mock_emit(job_id, {"step": "complete", "message": "Complete"})
    job = get_job(job_id)
    assert job["current_stage"] == "completed"
    assert job["status"] == "completed"


def test_progress_updates(setup_test_job):
    """Test that progress updates correctly across stages."""
    job_id = setup_test_job
    
    # Stage 1 starting
    update_job_status(job_id, "processing", progress=0.05, current_stage="paper_analysis")
    job = get_job(job_id)
    assert job["progress"] == 0.05
    assert job["current_stage"] == "paper_analysis"
    
    # Stage 1 complete
    update_job_status(job_id, "processing", progress=0.33, current_stage="code_execution")
    job = get_job(job_id)
    assert job["progress"] == 0.33
    assert job["current_stage"] == "code_execution"
    
    # Stage 2 complete
    update_job_status(job_id, "processing", progress=0.66, current_stage="evaluation")
    job = get_job(job_id)
    assert job["progress"] == 0.66
    assert job["current_stage"] == "evaluation"
    
    # Stage 3 complete
    update_job_status(job_id, "processing", progress=1.0, current_stage="evaluation")
    job = get_job(job_id)
    assert job["progress"] == 1.0
    assert job["current_stage"] == "evaluation"
    
    # Final completion
    update_job_status(job_id, "completed", progress=1.0, current_stage="completed")
    job = get_job(job_id)
    assert job["progress"] == 1.0
    assert job["current_stage"] == "completed"
    assert job["status"] == "completed"


def test_error_handling(setup_test_job):
    """Test error handling during analysis."""
    job_id = setup_test_job
    
    # Test error transition
    update_job_status(job_id, "failed", error_message="Test error", progress=0.0, current_stage="failed")
    job = get_job(job_id)
    assert job["status"] == "failed"
    assert job["current_stage"] == "failed"
    assert job["error_message"] == "Test error"


def test_evaluation_stage_persistence(setup_test_job):
    """Test that evaluation stage doesn't close prematurely."""
    job_id = setup_test_job
    
    # Simulate the problematic sequence:
    # 1. Stage 3 starting
    update_job_status(job_id, "processing", progress=0.67, current_stage="evaluation")
    job = get_job(job_id)
    assert job["current_stage"] == "evaluation"
    
    # 2. Stage 3 complete - should NOT close yet
    update_job_status(job_id, "processing", progress=1.0, current_stage="evaluation")
    job = get_job(job_id)
    assert job["current_stage"] == "evaluation", "Evaluation should stay active after stage_3_complete"
    assert job["status"] == "processing", "Should still be processing"
    
    # 3. Final complete - NOW it closes
    update_job_status(job_id, "completed", progress=1.0, current_stage="completed")
    job = get_job(job_id)
    assert job["current_stage"] == "completed"
    assert job["status"] == "completed"


@patch('services.job_service.get_db')
@patch('blueprints.jobs.extract_and_analyze_pdf')
@patch('blueprints.jobs.store_artifacts')
@patch('blueprints.jobs.spawn_agent_container')
@patch('blueprints.jobs.evaluate_reproducibility_aspects')
def test_full_pipeline_mocked(
    mock_eval,
    mock_spawn,
    mock_store,
    mock_extract,
    mock_db,
    mock_llm_provider,
    test_job_id
):
    """Test full analysis pipeline with all LLM calls mocked."""
    
    # Setup database mock
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock extraction to return test data
    mock_extract.return_value = (
        "test pdf content",
        {
            "artifacts": [
                {"url": "https://github.com/test/repo", "type": "github_repo"}
            ],
            "methodology": "test methodology",
            "claimed_results": "test results"
        }
    )
    
    # Mock evaluation to succeed
    mock_eval.return_value = True
    
    # Track emit_event calls
    emitted_steps = []
    original_emit = emit_event
    
    def track_emit(job_id, event):
        emitted_steps.append(event["step"])
        original_emit(job_id, event)
    
    with patch('blueprints.jobs.emit_event', side_effect=track_emit):
        with patch('blueprints.jobs.update_job_status') as mock_update:
            # Run pipeline
            try:
                analyze_paper_background(
                    test_job_id,
                    "/tmp/test.pdf",
                    {"container": "python", "model": "haiku"},
                    mock_llm_provider
                )
            except Exception as e:
                # May fail due to mocking, but we're checking the sequence
                print(f"Expected error during mocked pipeline: {e}")
    
    # Verify stage sequence
    assert "starting" in emitted_steps
    assert "stage_1_starting" in emitted_steps
    assert "stage_1_complete" in emitted_steps
    assert "stage_2_starting" in emitted_steps
    assert "stage_2_complete" in emitted_steps
    assert "stage_3_starting" in emitted_steps
    
    print(f"✓ Full pipeline test passed")
    print(f"  Emitted steps: {emitted_steps}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
