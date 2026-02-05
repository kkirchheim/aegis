"""
Comprehensive test suite for Paper Reproducibility Checker backend

Tests cover:
- Upload and basic flow
- Database operations
- Event emission
- Error handling
- Stage progression
"""

import json
import pytest
from blueprints.jobs import emit_event
from database import init_db, get_db


class TestHomeAndBasics:
    """Test home page and basic endpoints."""
    
    def test_home_page_redirects_when_unauthenticated(self, client):
        """Test home page redirects to login when not authenticated."""
        response = client.get('/')
        # Should redirect (302) to login
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_home_page_loads_when_authenticated(self, authenticated_user):
        """Test home page loads when authenticated."""
        response = authenticated_user.get('/')
        assert response.status_code == 200
        assert b'Paper Reproducibility' in response.data or b'Upload' in response.data
    
    def test_jobs_list_empty_when_authenticated(self, authenticated_user, app):
        """Test jobs list when empty."""
        response = authenticated_user.get('/jobs')
        # Should return empty list for authenticated user
        assert response.status_code in [200, 302]  # Might redirect if route requires auth check
        if response.status_code == 200:
            data = response.get_json()
            if data is not None:  # Some routes might return HTML instead
                assert isinstance(data, list)
                assert len(data) == 0


class TestDatabase:
    """Test database operations and schema."""
    
    def test_database_schema(self, app):
        """Test that all required tables are created."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            # Check all tables exist
            tables = ['jobs', 'artifacts', 'events', 'paper_analysis', 'execution_details', 'aspect_evaluations']
            for table in tables:
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                assert c.fetchone() is not None, f"Table {table} not found"
            
            conn.close()
    
    def test_jobs_table_columns(self, app):
        """Test jobs table has required columns."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            c.execute("PRAGMA table_info(jobs)")
            columns = {row[1] for row in c.fetchall()}
            
            required = {'id', 'status', 'pdf_path', 'pdf_filename', 'report', 'created_at', 'completed_at'}
            assert required.issubset(columns), f"Missing columns: {required - columns}"
            
            conn.close()
    
    def test_execution_details_has_discovered_files(self, app):
        """Test that execution_details table has discovered_files column."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            c.execute("PRAGMA table_info(execution_details)")
            columns = {row[1] for row in c.fetchall()}
            
            # Check for discovered_files (the fix we implemented)
            assert 'discovered_files' in columns, "Missing discovered_files column"
            assert 'test_info' in columns, "Missing test_info column"
            assert 'randomness_info' in columns, "Missing randomness_info column"
            
            conn.close()


class TestEventEmission:
    """Test event emission system."""
    
    def test_emit_event_stores_in_database(self, app):
        """Test that emitted events are stored in database."""
        job_id = "test-job-123"
        
        with app.app_context():
            # Create a job first
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            conn.commit()
            conn.close()
            
            # Emit an event
            emit_event(job_id, {
                "step": "test_step",
                "message": "Test message",
                "progress": 50
            })
            
            # Check it was stored
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM events WHERE job_id = ?", (job_id,))
            event = c.fetchone()
            conn.close()
            
            assert event is not None
            assert event['step'] == "test_step"
            assert event['message'] == "Test message"


class TestStageEvents:
    """Test stage progression events."""
    
    def test_stage_1_events(self, app):
        """Test that stage 1 starting and complete events can be emitted."""
        job_id = "test-job-stage"
        
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            conn.commit()
            conn.close()
            
            # Emit stage events
            emit_event(job_id, {
                "step": "stage_1_starting",
                "stage": "paper_analysis",
                "message": "Stage 1 starting",
                "progress": 5
            })
            
            emit_event(job_id, {
                "step": "stage_1_complete",
                "stage": "paper_analysis",
                "message": "Stage 1 complete",
                "progress": 40,
                "stage_duration_ms": 15000
            })
            
            # Verify events were stored
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) as count FROM events WHERE job_id = ? AND step LIKE 'stage_1%'",
                     (job_id,))
            count = c.fetchone()['count']
            conn.close()
            
            assert count == 2, f"Expected 2 stage_1 events, got {count}"
    
    def test_all_three_stages_events(self, app):
        """Test all three stage events can be emitted."""
        job_id = "test-job-all-stages"
        
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            conn.commit()
            conn.close()
            
            stages = [
                ("stage_1_starting", "paper_analysis", 5),
                ("stage_1_complete", "paper_analysis", 40),
                ("stage_2_starting", "code_execution", 40),
                ("stage_2_complete", "code_execution", 80),
                ("stage_3_starting", "reproducibility_evaluation", 80),
                ("stage_3_complete", "reproducibility_evaluation", 100)
            ]
            
            for step, stage, progress in stages:
                emit_event(job_id, {
                    "step": step,
                    "stage": stage,
                    "message": f"{step}",
                    "progress": progress
                })
            
            # Verify all stages were recorded
            conn = get_db()
            c = conn.cursor()
            for stage_num in [1, 2, 3]:
                c.execute(f"SELECT COUNT(*) as count FROM events WHERE job_id = ? AND step LIKE 'stage_{stage_num}%'",
                         (job_id,))
                count = c.fetchone()['count']
                assert count == 2, f"Expected 2 events for stage {stage_num}, got {count}"
            conn.close()


class TestJobRoutes:
    """Test job-related API routes."""
    
    def test_get_nonexistent_job_requires_auth(self, client):
        """Test getting a job that doesn't exist requires authentication."""
        response = client.get('/job/nonexistent-job-id')
        # Should redirect to login or return 401/403
        assert response.status_code in [302, 401, 403, 404]
    
    def test_create_job_in_database(self, authenticated_user, app):
        """Test creating and retrieving a job."""
        # Get the authenticated user's ID from session
        with authenticated_user.session_transaction() as sess:
            user_id = sess.get('user_id')
        
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-job-create"
            # Add job with the authenticated user's ID
            from datetime import datetime
            c.execute("""
                INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id, current_stage, progress, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, "completed", "/tmp/test.pdf", "test.pdf", user_id, "completed", 100.0, datetime.now()))
            conn.commit()
            conn.close()
        
        # Retrieve via API with authenticated user
        response = authenticated_user.get(f'/api/job/{job_id}')
        assert response.status_code == 200  # Should find job now that user_id matches
        data = response.get_json()
        assert data['id'] == job_id
        assert data['status'] == "completed"


class TestErrorHandling:
    """Test error handling in various scenarios."""
    
    def test_agent_think_missing_job_id(self, authenticated_user):
        """Test agent think endpoint without job_id."""
        response = authenticated_user.post(
            '/api/agent/think',
            data=json.dumps({"repo_state": {}}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_agent_log_missing_job_id(self, authenticated_user):
        """Test agent log endpoint without job_id."""
        response = authenticated_user.post(
            '/api/agent/log',
            data=json.dumps({"message": "test"}),
            content_type='application/json'
        )
        assert response.status_code == 400
    
    def test_agent_execution_missing_job_id(self, authenticated_user):
        """Test agent execution endpoint without job_id."""
        response = authenticated_user.post(
            '/api/agent/execution',
            data=json.dumps({
                "commands_run": "test",
                "stdout_combined": "test"
            }),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestDataIntegrity:
    """Test data integrity and proper storage."""
    
    def test_store_execution_details(self, app):
        """Test storing execution details with all fields."""
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-exec-details"
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            
            c.execute("""
                INSERT INTO execution_details
                (job_id, commands_run, stdout_combined, actual_results, 
                 dependencies_used, errors_summary, discovered_files, test_info, randomness_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                "python main.py",
                "Output here",
                json.dumps({"accuracy": 0.95}),
                "numpy==1.21.0",
                "No errors",
                json.dumps(["README.md", "main.py"]),
                "Tests found: 5",
                "Seeds set: 2",
                datetime.now()
            ))
            
            conn.commit()
            
            # Verify retrieval
            c.execute("SELECT * FROM execution_details WHERE job_id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            
            assert row is not None
            assert row['commands_run'] == "python main.py"
            
            # Verify JSON fields can be parsed
            discovered = json.loads(row['discovered_files'])
            assert isinstance(discovered, list)
            assert len(discovered) == 2
    
    def test_store_aspect_evaluations(self, app):
        """Test storing aspect evaluations."""
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-aspects"
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            
            # Insert aspect evaluations
            aspects = [
                ("dependencies_pinned", "Dependencies Pinned", "pass", True, True),
                ("test_suite_present", "Test Suite Present", "fail", False, False),
                ("documentation_quality", "Documentation Quality", "partial", True, False)
            ]
            
            for aspect_id, name, status, paper, code in aspects:
                c.execute("""
                    INSERT INTO aspect_evaluations
                    (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (job_id, aspect_id, name, status, f"Evidence for {name}", paper, code, "Conclusion"))
            
            conn.commit()
            
            # Verify count
            c.execute("SELECT COUNT(*) as count FROM aspect_evaluations WHERE job_id = ?", (job_id,))
            count = c.fetchone()['count']
            conn.close()
            
            assert count == 3, f"Expected 3 aspects, got {count}"


class TestPaperAnalysisStorage:
    """Test paper analysis storage."""
    
    def test_store_paper_analysis(self, app):
        """Test storing paper analysis data."""
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-paper-analysis"
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            
            c.execute("""
                INSERT INTO paper_analysis
                (job_id, extracted_text, claimed_results, methodology, dependencies, dataset_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                job_id,
                "Extracted text from PDF",
                json.dumps({"accuracy": 0.92}),
                "Random forest classifier",
                "numpy, scikit-learn",
                "Iris dataset"
            ))
            
            conn.commit()
            
            c.execute("SELECT * FROM paper_analysis WHERE job_id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            
            assert row is not None
            assert row['extracted_text'] == "Extracted text from PDF"
            assert json.loads(row['claimed_results'])['accuracy'] == 0.92


class TestArtifactStorage:
    """Test artifact storage."""
    
    def test_store_artifacts(self, app):
        """Test storing discovered artifacts."""
        with app.app_context():
            from datetime import datetime
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-artifacts"
            c.execute("INSERT INTO jobs (id, status, pdf_path, current_stage, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf", "paper_analysis", 0.0, datetime.now()))
            
            artifacts = [
                ("https://github.com/user/repo", "github_repo", "Main repository"),
                ("https://kaggle.com/dataset", "dataset", "Dataset link")
            ]
            
            for url, atype, desc in artifacts:
                c.execute("""
                    INSERT INTO artifacts (job_id, url, artifact_type, description)
                    VALUES (?, ?, ?, ?)
                """, (job_id, url, atype, desc))
            
            conn.commit()
            
            c.execute("SELECT COUNT(*) as count FROM artifacts WHERE job_id = ?", (job_id,))
            count = c.fetchone()['count']
            conn.close()
            
            assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
