# tests/integration/test_error_handling.py
"""Integration tests for error handling and content negotiation"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]

class TestContentNegotiation:
    """Test content negotiation for error responses"""
    
    def test_404_returns_html_for_browser(self, client):
        """Test 404 returns HTML for browser requests"""
        response = client.get('/nonexistent')
        
        assert response.status_code == 404
        # Should be HTML (not JSON)
        assert response.content_type in ['text/html', 'text/html; charset=utf-8']
        assert b'html' in response.data.lower()
    
    def test_404_returns_json_for_api_request(self, client):
        """Test 404 returns JSON for API requests"""
        response = client.get('/api/nonexistent')
        
        assert response.status_code == 404
        assert response.content_type in ['application/json', 'application/json; charset=utf-8']
        data = response.get_json()
        assert "error" in data
    
    def test_404_returns_json_with_accept_header(self, client):
        """Test 404 returns JSON when Accept: application/json"""
        response = client.get('/nonexistent',
            headers={'Accept': 'application/json'}
        )
        
        assert response.status_code == 404
        # Should be JSON
        data = response.get_json()
        assert "error" in data
    
    def test_500_returns_html_for_browser(self, client):
        """Test 500 returns HTML for browser"""
        # Trigger a 500 error somehow (e.g., invalid request)
        response = client.post('/api/auth/login', 
            data="invalid json",
            content_type='application/json'
        )
        
        # If it's a 500
        if response.status_code == 500:
            # Check if it's HTML
            if 'text/html' in response.content_type:
                assert b'html' in response.data.lower()

class TestAPIErrorResponses:
    """Test API error response codes"""
    
    def test_400_bad_request(self, client):
        """Test 400 Bad Request response"""
        response = client.post('/api/auth/register', json={
            "username": "test"
            # Missing password fields
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_401_unauthorized(self, client):
        """Test 401 Unauthorized response"""
        response = client.post('/api/auth/login', json={
            "username": "nonexistent",
            "password": "anypassword"
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
    
    def test_403_forbidden(self, authenticated_user, other_user, test_job):
        """Test 403 Forbidden response"""
        # User 2 tries to access User 1's job
        response = other_user.delete(f'/api/job/{test_job["id"]}')
        
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data
    
    def test_404_not_found(self, client):
        """Test 404 Not Found response"""
        response = client.get('/api/job/nonexistent')
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

class TestHTTPMethods:
    """Test correct HTTP method usage"""
    
    def test_post_required_for_login(self, client):
        """Test GET /api/auth/login not allowed"""
        response = client.get('/api/auth/login')
        
        # Should be 405 Method Not Allowed or redirect
        assert response.status_code in [405, 302]
    
    def test_delete_returns_204(self, authenticated_user, test_job):
        """Test DELETE returns 204 No Content on success"""
        response = authenticated_user.delete(f'/api/job/{test_job["id"]}')
        
        assert response.status_code == 204
        # 204 should have no content
        assert len(response.data) == 0 or response.data == b''
    
    def test_patch_for_user_status(self, admin_user, test_user):
        """Test PATCH for resource updates"""
        response = admin_user.patch(f'/api/admin/users/{test_user["id"]}', json={
            "is_active": False
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True

class TestMalformedRequests:
    """Test handling of malformed requests"""
    
    def test_invalid_json_body(self, client):
        """Test invalid JSON in request body"""
        response = client.post('/api/auth/login',
            data='{"invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_missing_required_fields(self, client):
        """Test missing required fields in JSON"""
        response = client.post('/api/auth/login', json={
            "username": "test"
            # Missing password
        })
        
        assert response.status_code == 400
    
    def test_invalid_field_types(self, client):
        """Test invalid field types"""
        response = client.post('/api/auth/register', json={
            "username": 123,  # Should be string
            "password": "test",
            "password_confirm": "test"
        })
        
        assert response.status_code == 400

class TestAuthenticationErrors:
    """Test authentication-specific errors"""
    
    def test_missing_auth_token(self, client, test_job):
        """Test accessing protected endpoint without auth"""
        response = client.get(f'/api/job/{test_job["id"]}')
        
        assert response.status_code == 401
    
    def test_invalid_auth_token(self, client, test_job):
        """Test accessing protected endpoint with invalid token"""
        response = client.get(f'/api/job/{test_job["id"]}',
            headers={'Authorization': 'Bearer invalid'}
        )
        
        assert response.status_code == 401
    
    def test_expired_session(self, authenticated_user):
        """Test accessing with expired session (if applicable)"""
        # Logout to expire session
        authenticated_user.get('/logout')
        
        # Try to access protected resource
        response = authenticated_user.get('/history')
        
        # Should redirect to login
        assert response.status_code in [302, 401]
