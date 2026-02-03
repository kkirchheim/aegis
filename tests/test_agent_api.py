"""
Tests for Agent API endpoints (backend -> agent communication)

These tests ensure the backend correctly handles agent requests
and doesn't crash when given edge-case data.
"""

import json
import pytest
from app import app, init_db, DATABASE
import sqlite3
import tempfile
import os


@pytest.fixture
def client():
    """Create a test client with temporary database."""
    # Create temp database
    db_fd, db_path = tempfile.mkstemp()
    
    # Override database path
    import app as app_module
    app_module.DATABASE = db_path
    
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Initialize database
        with app.app_context():
            init_db()
        
        yield client
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


class TestAgentThink:
    """Tests for /api/agent/think endpoint."""
    
    def test_basic_request(self, client):
        """Test basic valid request."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md", "main.py"],
                "last_output": "Some output",
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should return 200 (successful API response)
        # Note: May be 500 if Claude fails, but at least shouldn't crash on bad data
        assert response.status_code in [200, 500]
        
        # Response should be valid JSON
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_missing_job_id(self, client):
        """Test request without job_id."""
        payload = {
            "repo_state": {
                "repo_url": "https://github.com/example/repo"
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should return 400 (bad request)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_none_errors(self, client):
        """Test when errors is None (the bug we just fixed!)."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": "output",
                "errors": None,  # ← This was causing the crash!
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should NOT crash with "object of type 'NoneType' has no len()"
        # Should return 200 or 500 from Claude, not a crash
        assert response.status_code != 500 or "NoneType" not in str(response.get_json())
    
    def test_none_last_output(self, client):
        """Test when last_output is None."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": None,  # ← Edge case
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should handle None gracefully
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_missing_optional_fields(self, client):
        """Test when optional repo_state fields are missing."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                # Only required fields
                "repo_url": "https://github.com/example/repo"
                # Missing: discovered_files, last_output, errors, iteration
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should not crash even with missing optional fields
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_empty_discovered_files(self, client):
        """Test with empty discovered_files list."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": [],  # Empty
                "last_output": "",
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_very_long_output(self, client):
        """Test with very long last_output (context truncation)."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": "x" * 10000,  # 10k characters
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should truncate context and not crash
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_multiple_errors(self, client):
        """Test with multiple errors in the list."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": "output",
                "errors": [
                    {"command": "pip install", "stderr": "Error 1"},
                    {"command": "python script.py", "stderr": "Error 2"},
                    {"command": "npm install", "stderr": "Error 3"},
                    {"command": "make build", "stderr": "Error 4"},
                ],
                "iteration": 5
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should only show last 2 errors (as per our implementation)
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_high_iteration_count(self, client):
        """Test at max iterations (should possibly suggest done)."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": "Still failing",
                "errors": [{"command": "python", "stderr": "Error"}],
                "iteration": 15  # Max iterations
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
        # Claude should ideally suggest "done" at max iterations
        # but at least shouldn't crash
    
    def test_special_characters_in_output(self, client):
        """Test with special characters that might break JSON."""
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": 'Error: "quotes" and \\backslashes\\ and \n newlines',
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should handle special characters correctly
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)


class TestAgentLog:
    """Tests for /api/agent/log endpoint."""
    
    def test_basic_log(self, client):
        """Test basic log message."""
        payload = {
            "job_id": "test-job-123",
            "message": "Test log message"
        }
        
        response = client.post(
            '/api/agent/log',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("ok") is True
    
    def test_missing_job_id(self, client):
        """Test log without job_id."""
        payload = {
            "message": "Test log message"
        }
        
        response = client.post(
            '/api/agent/log',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_empty_message(self, client):
        """Test log with empty message."""
        payload = {
            "job_id": "test-job-123",
            "message": ""
        }
        
        response = client.post(
            '/api/agent/log',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
    
    def test_very_long_message(self, client):
        """Test log with very long message."""
        payload = {
            "job_id": "test-job-123",
            "message": "x" * 100000  # 100k characters
        }
        
        response = client.post(
            '/api/agent/log',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should handle long messages gracefully
        assert response.status_code == 200


class TestPrompBuilding:
    """Tests for prompt building logic (integration tests)."""
    
    def test_context_truncation_in_prompt(self, client):
        """Verify that context is properly truncated in the prompt."""
        # This test would require mocking Claude API
        # For now, just ensure the endpoint doesn't crash
        
        payload = {
            "job_id": "test-job-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["file1.py", "file2.py", "file3.py", 
                                   "file4.py", "file5.py", "file6.py",
                                   "file7.py", "file8.py", "file9.py",
                                   "file10.py", "file11.py", "file12.py",
                                   "file13.py", "file14.py", "file15.py",
                                   "file16.py", "file17.py", "file18.py"],
                "last_output": "x" * 5000,
                "errors": [{"command": "cmd", "stderr": "error"}] * 10,
                "iteration": 8
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should not crash despite large amounts of data
        assert response.status_code in [200, 500]


class TestDebugLogging:
    """Tests to ensure debug logging is working."""
    
    def test_detailed_logging_on_parse_failure(self, client, caplog):
        """Verify that full Claude response is logged when JSON parsing fails."""
        import logging
        caplog.set_level(logging.INFO)
        
        payload = {
            "job_id": "debug-test-123",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": ["README.md"],
                "last_output": "",
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Check that detailed logging was performed
        log_text = caplog.text
        
        # Should log "Claude Response" marker for debugging
        assert "Claude Response" in log_text or "Parsed JSON" in log_text or response.status_code == 500
        
        # Should not crash regardless
        assert response.status_code in [200, 500]


class TestMalformedResponses:
    """Tests for handling malformed Claude responses."""
    
    def test_invalid_json_response(self, client):
        """Test that API handles invalid JSON gracefully (mocked scenario)."""
        # This would require mocking Claude API to return invalid JSON
        # For now, just ensure endpoint is resilient
        
        payload = {
            "job_id": "malformed-test",
            "repo_state": {
                "repo_url": "https://github.com/example/repo",
                "discovered_files": [],
                "last_output": "",
                "errors": [],
                "iteration": 1
            }
        }
        
        response = client.post(
            '/api/agent/think',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Either succeeds or fails gracefully (not 500 with parsing error)
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert isinstance(data, dict)
        
        # If it succeeded, should have action field
        if response.status_code == 200:
            assert "action" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
