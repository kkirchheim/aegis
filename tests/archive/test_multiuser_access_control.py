"""
Tests for multi-user access control in Paper Reproducibility Checker.

Tests verify:
- Jobs are isolated per user
- Users cannot access other users' jobs (403 Forbidden)
- All protected routes require authentication
- Logout endpoint works for both GET and POST
- User can only see their own jobs in /jobs list
"""

import json
import pytest
import tempfile
import os
from app import app, init_db, get_db, DATABASE
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


class TestMultiUserAccessControl:
    """Test multi-user access control and job isolation."""
    
    def test_unauthenticated_access_denied(self, client):
        """Test that unauthenticated requests are denied."""
        # /jobs should redirect to login
        response = client.get('/jobs', follow_redirects=False)
        assert response.status_code == 401
        
        # /upload should deny
        response = client.post('/upload', data={'pdf': b'test'})
        assert response.status_code == 401
    
    def test_register_user(self, client):
        """Test user registration."""
        response = client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'Registration successful'
    
    def test_login_user(self, client):
        """Test user login."""
        # Register first
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        # Login
        response = client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'
    
    def test_logout_post_endpoint(self, client):
        """Test POST /logout endpoint."""
        # Register and login
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        # Logout via POST
        response = client.post('/logout', follow_redirects=False)
        
        # Should redirect to /login
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_logout_get_endpoint(self, client):
        """Test GET /logout endpoint."""
        # Register and login
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        # Logout via GET
        response = client.get('/logout', follow_redirects=False)
        
        # Should redirect to /login
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_logout_clears_session(self, client):
        """Test that logout clears the session."""
        # Register and login
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        # Logout
        client.post('/logout')
        
        # Now trying to access protected routes should fail
        response = client.get('/jobs')
        assert response.status_code == 401
    
    def test_jobs_list_filtered_by_user(self, client):
        """Test that /jobs returns only current user's jobs."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Insert a mock job for user 1 directly in DB
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id)
            )
            conn.commit()
            conn.close()
        
        # Get jobs for user 1
        response = client.get('/jobs')
        assert response.status_code == 200
        jobs = response.get_json()
        assert len(jobs) == 1
        assert jobs[0]['id'] == 'job1-user1'
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Insert a mock job for user 2
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user2',))
            user2_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user2', 'completed', '/path/to/pdf2.pdf', 'pdf2.pdf', user2_id)
            )
            conn.commit()
            conn.close()
        
        # Get jobs for user 2 - should only see user2's job
        response = client.get('/jobs')
        assert response.status_code == 200
        jobs = response.get_json()
        assert len(jobs) == 1
        assert jobs[0]['id'] == 'job1-user2'
    
    def test_get_job_403_different_user(self, client):
        """Test that user cannot access another user's job."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Create a job for user 1
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id, report) VALUES (?, ?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id, '{}')
            )
            conn.commit()
            conn.close()
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Try to access user1's job - should get 403
        response = client.get('/job/job1-user1')
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Access denied'
    
    def test_get_job_404_nonexistent(self, client):
        """Test that accessing nonexistent job returns 404."""
        # Register and login
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        # Try to access nonexistent job
        response = client.get('/job/nonexistent-job')
        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Job not found'
    
    def test_delete_job_403_different_user(self, client):
        """Test that user cannot delete another user's job."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Create a job for user 1
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id)
            )
            conn.commit()
            conn.close()
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Try to delete user1's job - should get 403
        response = client.delete('/job/job1-user1')
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Access denied'
    
    def test_chat_endpoint_403_different_user(self, client):
        """Test that user cannot chat with another user's job."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Create a job for user 1
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id)
            )
            conn.commit()
            conn.close()
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Try to chat with user1's job - should get 403
        response = client.post('/api/job/job1-user1/chat', 
            json={'message': 'Tell me about this paper'})
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Access denied'
    
    def test_chat_history_403_different_user(self, client):
        """Test that user cannot access another user's chat history."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Create a job for user 1
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id)
            )
            conn.commit()
            conn.close()
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Try to get chat history for user1's job - should get 403
        response = client.get('/api/job/job1-user1/chat/history')
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Access denied'
    
    def test_full_job_data_403_different_user(self, client):
        """Test that user cannot access another user's full job data."""
        # Register and login user 1
        client.post('/register', data={
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        client.post('/login', data={
            'username': 'user1',
            'password': 'password123'
        })
        
        # Create a job for user 1
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('user1',))
            user1_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id) VALUES (?, ?, ?, ?, ?)",
                ('job1-user1', 'completed', '/path/to/pdf1.pdf', 'pdf1.pdf', user1_id)
            )
            conn.commit()
            conn.close()
        
        # Logout user 1
        client.post('/logout')
        
        # Register and login user 2
        client.post('/register', data={
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password456',
            'confirm_password': 'password456'
        })
        
        client.post('/login', data={
            'username': 'user2',
            'password': 'password456'
        })
        
        # Try to access user1's full job data - should get 403
        response = client.get('/api/job/job1-user1/full')
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Access denied'
    
    def test_protected_routes_require_auth(self, client):
        """Test that all protected routes require authentication."""
        protected_routes = [
            ('/jobs', 'GET'),
            ('/upload', 'POST'),
        ]
        
        for route, method in protected_routes:
            if method == 'GET':
                response = client.get(route)
            else:
                response = client.post(route, data={})
            
            assert response.status_code == 401, f"Route {method} {route} should require auth"
    
    def test_owner_can_access_own_job(self, client):
        """Test that user can access their own job."""
        # Register and login
        client.post('/register', data={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        })
        
        client.post('/login', data={
            'username': 'testuser1',
            'password': 'securepass123'
        })
        
        # Create a job for this user
        with app.app_context():
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", ('testuser1',))
            user_id = c.fetchone()[0]
            
            c.execute(
                "INSERT INTO jobs (id, status, pdf_path, pdf_filename, user_id, report) VALUES (?, ?, ?, ?, ?, ?)",
                ('myjob1', 'completed', '/path/to/pdf.pdf', 'pdf.pdf', user_id, '{}')
            )
            conn.commit()
            conn.close()
        
        # Access own job - should succeed
        response = client.get('/job/myjob1')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 'myjob1'
        assert data['status'] == 'completed'
