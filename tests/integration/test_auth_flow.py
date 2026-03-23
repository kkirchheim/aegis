"""Integration tests for authentication flow"""

import pytest
import json
import uuid

pytestmark = [pytest.mark.integration, pytest.mark.api, pytest.mark.auth]


class TestAuthRegistration:
    """Test user registration endpoint"""
    
    def test_register_valid_user(self, client):
        """Test registering with valid credentials"""
        unique_id = str(uuid.uuid4())[:8]
        response = client.post('/api/auth/register', json={
            "username": f"newuser_{unique_id}",
            "email": f"newuser_{unique_id}@example.com",
            "password": "ValidPass123!",
            "confirm_password": "ValidPass123!"
        })
        
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert "message" in data or "redirect" in data
        assert data.get("redirect") == "/login"
    
    def test_register_duplicate_username(self, client):
        """Test registering with existing username"""
        # First registration should succeed
        response1 = client.post('/api/auth/register', json={
            "username": "uniqueuser",
            "email": "unique@example.com",
            "password": "ValidPass123!",
            "confirm_password": "ValidPass123!"
        })
        assert response1.status_code in [200, 201]
        
        # Second registration with same username should fail (403 or 400)
        response2 = client.post('/api/auth/register', json={
            "username": "uniqueuser",
            "email": "different@example.com",
            "password": "ValidPass456!",
            "confirm_password": "ValidPass456!"
        })
        
        assert response2.status_code == 409
        data = response2.get_json()
        assert "error" in data
        assert data["error"] is not None
    
    def test_register_password_mismatch(self, client):
        """Test registering with mismatched passwords"""
        unique_id = str(uuid.uuid4())[:8]
        response = client.post('/api/auth/register', json={
            "username": f"newuser_{unique_id}",
            "email": f"newuser_{unique_id}@example.com",
            "password": "ValidPass123!",
            "confirm_password": "DifferentPass123!"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "password" in data["error"].lower()
    
    def test_register_missing_fields(self, client):
        """Test registering without required fields"""
        unique_id = str(uuid.uuid4())[:8]
        response = client.post('/api/auth/register', json={
            "username": f"newuser_{unique_id}"
            # Missing password fields
        })

        assert response.status_code in (400, 422)

class TestAuthLogin:
    """Test user login endpoint"""
    
    def test_login_valid_credentials(self, client, app):
        """Test logging in with correct credentials"""
        # First, register a user
        username = "logintest"
        password = "LoginTest123!"
        email = "logintest@example.com"
        
        register_response = client.post('/api/auth/register', json={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password
        })
        assert register_response.status_code in [200, 201]
        
        # Manually activate the user in database for testing
        from services.auth_service import get_user_by_username
        
        with app.app_context():
            user = get_user_by_username(username)
            if user:
                # Manually activate for testing
                user.is_active = True
                user.save()
        
        response = client.post('/api/auth/login', json={
            "username": username,
            "password": password
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data or "redirect" in data
    
    def test_login_invalid_password(self, client, app):
        """Test logging in with wrong password"""
        unique_id = str(uuid.uuid4())[:8]
        username = f"user_{unique_id}"
        email = f"user_{unique_id}@example.com"
        password = "ValidPass123!"
        
        # First, register a user
        register_response = client.post('/api/auth/register', json={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password
        })
        assert register_response.status_code in [200, 201]
        
        # Manually activate the user
        from services.auth_service import get_user_by_username
        
        with app.app_context():
            user = get_user_by_username(username)
            if user:
                user.is_active = True
                user.save()
        
        # Try to login with wrong password
        response = client.post('/api/auth/login', json={
            "username": username,
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert data["error"] is not None
    
    def test_login_nonexistent_user(self, client):
        """Test logging in with non-existent user"""
        response = client.post('/api/auth/login', json={
            "username": "nonexistent",
            "password": "anypassword"
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

class TestAuthPages:
    """Test auth page routes (GET)"""
    
    def test_login_page(self, client):
        """Test login page loads"""
        response = client.get('/login')
        
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'password' in response.data.lower()
    
    def test_register_page(self, client):
        """Test register page loads"""
        response = client.get('/register')
        
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'password' in response.data.lower()
    
    def test_profile_page_requires_auth(self, client):
        """Test profile page requires authentication"""
        response = client.get('/profile')
        
        # Should redirect to login if not authenticated (302) or be forbidden (403/401)
        assert response.status_code in [302, 401, 403]

class TestChangePassword:
    """Test change password endpoint"""
    
    def test_change_password_valid(self, authenticated_user, test_user_credentials):
        """Test changing password successfully"""
        # authenticated_user fixture already has the session set
        response = authenticated_user.post('/api/auth/change-password', json={
            "old_password": test_user_credentials["password"],
            "new_password": "NewPass456!",
            "confirm_password": "NewPass456!"
        })

        assert response.status_code == 204
    
    def test_change_password_wrong_current(self, authenticated_user):
        """Test changing password with wrong current password"""
        response = authenticated_user.post('/api/auth/change-password', json={
            "old_password": "wrongpassword",
            "new_password": "NewPass456!",
            "confirm_password": "NewPass456!"
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
    
    def test_change_password_mismatch(self, authenticated_user, test_user_credentials):
        """Test new passwords don't match"""
        response = authenticated_user.post('/api/auth/change-password', json={
            "old_password": test_user_credentials["password"],
            "new_password": "NewPass456!",
            "confirm_password": "DifferentPass789!"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
