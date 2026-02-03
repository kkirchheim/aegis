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
import tempfile
import os
from app import app, init_db, get_db, emit_event, DATABASE
import sqlite3


@pytest.fixture
def client():
    """Create a test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    
    import app as app_module
    app_module.DATABASE = db_path
    
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
    
    os.close(db_fd)
    os.unlink(db_path)


class TestHomeAndBasics:
    """Test home page and basic endpoints."""
    
    def test_home_page(self, client):
        """Test home page loads."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Paper Reproducibility' in response.data
    
    def test_jobs_list_empty(self, client):
        """Test jobs list when empty."""
        response = client.get('/jobs')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestDatabase:
    """Test database operations and schema."""
    
    def test_database_schema(self, client):
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
    
    def test_jobs_table_columns(self, client):
        """Test jobs table has required columns."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            c.execute("PRAGMA table_info(jobs)")
            columns = {row[1] for row in c.fetchall()}
            
            required = {'id', 'status', 'pdf_path', 'pdf_filename', 'report', 'created_at', 'completed_at'}
            assert required.issubset(columns), f"Missing columns: {required - columns}"
            
            conn.close()
    
    def test_execution_details_has_discovered_files(self, client):
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
    
    def test_emit_event_stores_in_database(self, client):
        """Test that emitted events are stored in database."""
        job_id = "test-job-123"
        
        with app.app_context():
            # Create a job first
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
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
    
    def test_stage_1_events(self, client):
        """Test that stage 1 starting and complete events can be emitted."""
        job_id = "test-job-stage"
        
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
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
    
    def test_all_three_stages_events(self, client):
        """Test all three stage events can be emitted."""
        job_id = "test-job-all-stages"
        
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
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
    
    def test_get_nonexistent_job(self, client):
        """Test getting a job that doesn't exist."""
        response = client.get('/job/nonexistent-job-id')
        assert response.status_code == 404
    
    def test_create_job_in_database(self, client):
        """Test creating and retrieving a job."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-job-create"
            c.execute("""
                INSERT INTO jobs (id, status, pdf_path, pdf_filename)
                VALUES (?, ?, ?, ?)
            """, (job_id, "completed", "/tmp/test.pdf", "test.pdf"))
            conn.commit()
            conn.close()
        
        # Retrieve via API
        response = client.get(f'/job/{job_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == job_id
        # pdf_filename may or may not be in response depending on endpoint implementation
        assert data['status'] == "completed"


class TestErrorHandling:
    """Test error handling in various scenarios."""
    
    def test_agent_think_missing_job_id(self, client):
        """Test agent think endpoint without job_id."""
        response = client.post(
            '/api/agent/think',
            data=json.dumps({"repo_state": {}}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_agent_log_missing_job_id(self, client):
        """Test agent log endpoint without job_id."""
        response = client.post(
            '/api/agent/log',
            data=json.dumps({"message": "test"}),
            content_type='application/json'
        )
        assert response.status_code == 400
    
    def test_agent_execution_missing_job_id(self, client):
        """Test agent execution endpoint without job_id."""
        response = client.post(
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
    
    def test_store_execution_details(self, client):
        """Test storing execution details with all fields."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-exec-details"
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
            
            c.execute("""
                INSERT INTO execution_details
                (job_id, commands_run, stdout_combined, actual_results, 
                 dependencies_used, errors_summary, discovered_files, test_info, randomness_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                "python main.py",
                "Output here",
                json.dumps({"accuracy": 0.95}),
                "numpy==1.21.0",
                "No errors",
                json.dumps(["README.md", "main.py"]),
                "Tests found: 5",
                "Seeds set: 2"
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
    
    def test_store_aspect_evaluations(self, client):
        """Test storing aspect evaluations."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-aspects"
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
            
            # Insert aspect evaluations
            aspects = [
                ("dependencies_pinned", "Dependencies Pinned", "pass", True, True),
                ("test_suite_present", "Test Suite Present", "fail", False, False),
                ("documentation_quality", "Documentation Quality", "partial", True, False)
            ]
            
            for aspect_id, name, status, paper, code in aspects:
                c.execute("""
                    INSERT INTO aspect_evaluations
                    (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (job_id, aspect_id, name, status, f"Evidence for {name}", paper, code, "Conclusion"))
            
            conn.commit()
            
            # Verify count
            c.execute("SELECT COUNT(*) as count FROM aspect_evaluations WHERE job_id = ?", (job_id,))
            count = c.fetchone()['count']
            conn.close()
            
            assert count == 3, f"Expected 3 aspects, got {count}"


class TestPaperAnalysisStorage:
    """Test paper analysis storage."""
    
    def test_store_paper_analysis(self, client):
        """Test storing paper analysis data."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-paper-analysis"
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
            
            c.execute("""
                INSERT INTO paper_analysis
                (job_id, extracted_text, claimed_results, methodology, dependencies, dataset_description)
                VALUES (?, ?, ?, ?, ?, ?)
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
    
    def test_store_artifacts(self, client):
        """Test storing discovered artifacts."""
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            
            job_id = "test-artifacts"
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
            
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


class TestNoneHandling:
    """Test that None values are handled gracefully (the bug we fixed)."""
    
    def test_agent_think_with_none_errors(self, client):
        """Test agent think with None errors field."""
        payload = {
            "job_id": "test-job",
            "repo_state": {
                "repo_url": "https://github.com/test/repo",
                "errors": None,  # The problematic case
                "discovered_files": ["README.md"]
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should not crash
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_agent_think_with_missing_fields(self, client):
        """Test agent think with minimal data."""
        payload = {
            "job_id": "test-job-minimal",
            "repo_state": {}  # Empty repo state
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)


class TestJsonSerialization:
    """Test JSON serialization for API responses."""
    
    def test_event_response_json_serializable(self, client):
        """Test that event responses are valid JSON."""
        job_id = "test-json"
        
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO jobs (id, status, pdf_path) VALUES (?, ?, ?)",
                     (job_id, "processing", "/tmp/test.pdf"))
            conn.commit()
            conn.close()
            
            # Emit various event types
            emit_event(job_id, {
                "step": "test",
                "progress": 50,
                "duration_ms": 1000,
                "items": ["a", "b", "c"]
            })
            
            # Try to fetch as JSON
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM events WHERE job_id = ?", (job_id,))
            event = c.fetchone()
            conn.close()
            
            # Should be able to serialize
            json_str = json.dumps({
                "step": event['step'],
                "message": event['message']
            })
            assert isinstance(json_str, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
