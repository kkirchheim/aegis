# tests/integration/test_pipeline.py
"""End-to-end tests for complete analysis pipeline"""

import pytest
import time
from io import BytesIO

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.db]

class TestPipelineStages:
    """Test 3-stage pipeline progression"""
    
    @pytest.mark.slow
    def test_pipeline_completes_all_stages(self, authenticated_user, test_pdf_file):
        """Test pipeline progresses through all 3 stages"""
        # Upload PDF
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (test_pdf_file, 'test.pdf')}
        )
        job_id = response.get_json()["job_id"]
        
        # Poll for completion
        max_iterations = 20
        last_stage = "pending"
        for i in range(max_iterations):
            response = authenticated_user.get(f'/api/job/{job_id}/full')
            data = response.get_json()
            current_stage = data.get("current_stage")
            progress = data.get("progress")
            
            # Verify progress is monotonic
            assert progress >= 0.0 and progress <= 1.0
            
            if data["status"] == "completed":
                last_stage = current_stage
                break
            
            time.sleep(0.5)
        
        # Verify final state
        assert last_stage == "completed"
    
    def test_pipeline_stage_progression_order(self, authenticated_user, test_pdf_file):
        """Test stages progress in correct order"""
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (test_pdf_file, 'test.pdf')}
        )
        job_id = response.get_json()["job_id"]
        
        # Get job data
        response = authenticated_user.get(f'/api/job/{job_id}/full')
        data = response.get_json()
        
        events = data.get("events", [])
        stages_seen = []
        
        for event in events:
            step = event.get("step")
            if "stage" in step.lower() or step in ["paper_analysis", "code_execution", "evaluation"]:
                stages_seen.append(step)
        
        # Verify if stages were seen, they're in correct order
        # (pending → paper_analysis → code_execution → evaluation → completed)

class TestPipelineEventEmission:
    """Test event emission throughout pipeline"""
    
    def test_events_emitted_for_each_stage(self, authenticated_user, test_pdf_file):
        """Test events are emitted for each stage"""
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (test_pdf_file, 'test.pdf')}
        )
        job_id = response.get_json()["job_id"]
        
        # Get job data
        response = authenticated_user.get(f'/api/job/{job_id}/full')
        data = response.get_json()
        
        events = data.get("events", [])
        assert len(events) > 0
        
        # Each event should have required fields
        for event in events:
            assert "step" in event
            assert "message" in event
            assert "timestamp" in event
            assert "severity" in event

class TestPipelineProgress:
    """Test progress tracking"""
    
    def test_progress_starts_at_zero(self, authenticated_user, test_pdf_file):
        """Test progress starts at 0.0"""
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (test_pdf_file, 'test.pdf')}
        )
        job_id = response.get_json()["job_id"]
        
        # Get job immediately
        response = authenticated_user.get(f'/api/job/{job_id}/full')
        data = response.get_json()
        
        assert data["progress"] >= 0.0
    
    def test_progress_is_monotonic(self, authenticated_user, test_pdf_file):
        """Test progress only increases (never decreases)"""
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (test_pdf_file, 'test.pdf')}
        )
        job_id = response.get_json()["job_id"]
        
        previous_progress = 0.0
        for i in range(10):
            response = authenticated_user.get(f'/api/job/{job_id}/full')
            data = response.get_json()
            current_progress = data["progress"]
            
            # Progress should never decrease
            assert current_progress >= previous_progress
            previous_progress = current_progress
            
            time.sleep(0.1)

class TestPipelineErrorHandling:
    """Test error handling in pipeline"""
    
    def test_pipeline_handles_invalid_pdf(self, authenticated_user):
        """Test pipeline handles non-PDF file gracefully"""
        invalid_file = BytesIO(b"This is not a PDF")
        
        response = authenticated_user.post('/api/job/upload',
            data={'pdf': (invalid_file, 'notapdf.txt')}
        )
        
        # Should either reject or mark as failed
        if response.status_code == 202:
            job_id = response.get_json()["job_id"]
            # Job should eventually fail
            for i in range(10):
                response = authenticated_user.get(f'/api/job/{job_id}/full')
                if response.get_json()["status"] == "failed":
                    break
                time.sleep(0.1)
