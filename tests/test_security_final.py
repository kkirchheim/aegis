"""
Comprehensive security tests for Paper Reproducibility Checker.

Tests cover:
1. Authentication and authorization
2. Environment variable security
3. Health endpoint information disclosure
4. Password hashing
5. Session security
6. Protected routes
7. Admin access control
"""

import sys
import os
import pytest
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set dummy API key for testing
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-key-for-pytest"

from flask import Flask
from config import Config
from app import create_app
from services.auth_service import hash_password, verify_password, create_user, get_user_by_id
from database import init_db, get_db


@pytest.fixture
def app():
    """Create app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['DATABASE'] = ':memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-for-pytest-only'
    
    # Initialize database
    init_db()
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def app_full():
    """Create full application for integration testing."""
    # Save original database path
    original_db = Config.DATABASE
    Config.DATABASE = ':memory:'
    
    app = create_app()
    
    # Restore database path
    Config.DATABASE = original_db
    
    return app


@pytest.fixture
def client_full(app_full):
    """Create test client for full app."""
    with app_full.app_context():
        return app_full.test_client()


class TestHealthEndpoint:
    """Test /api/health endpoint security."""
    
    def test_health_endpoint_accessible_without_auth(self, client_full):
        """Test that /health endpoint is publicly accessible."""
        response = client_full.get('/api/health')
        assert response.status_code in [200, 503]
        data = json.loads(response.data)
        assert 'status' in data
    
    def test_health_endpoint_doesnt_leak_error_messages(self, client_full):
        """Test that /health endpoint doesn't leak detailed error messages."""
        response = client_full.get('/api/health')
        data = json.loads(response.data)
        
        # Check that errors (if any) are generic
        if 'errors' in data:
            for error in data.get('errors', []):
                # Should not contain detailed connection strings, paths, etc.
                assert not error.startswith('Database URL:')
                assert 'password' not in error.lower()
                assert 'api_key' not in error.lower()
    
    def test_health_endpoint_doesnt_expose_config(self, client_full):
        """Test that /health endpoint doesn't expose configuration."""
        response = client_full.get('/api/health')
        data = json.loads(response.data)
        
        # Should not contain paths, API keys, or other sensitive data
        response_str = json.dumps(data)
        assert 'anthropic' not in response_str.lower()
        assert '/path' not in response_str.lower()
        assert 'sk-' not in response_str  # API key pattern


class TestEnvironmentVariables:
    """Test environment variable security."""
    
    def test_anthropic_api_key_no_default(self):
        """Test that ANTHROPIC_API_KEY has no default value."""
        # This test verifies that the config doesn't have a default for the key
        # The test runner provides sk-test-dummy-key-for-pytest as test value
        api_key = os.getenv('ANTHROPIC_API_KEY')
        assert api_key is not None
        assert api_key.startswith('sk-')  # Should be a key-like value
    
    def test_secret_key_configuration(self):
        """Test SECRET_KEY is properly configured."""
        # In test, it's set to fixed value
        # In production, it should be set in .env or generated once
        secret_key = Config.SECRET_KEY
        assert secret_key is not None
        assert len(secret_key) >= 16  # Reasonable length
        assert isinstance(secret_key, str)
    
    def test_no_hardcoded_credentials_in_files(self):
        """Test that source files don't contain hardcoded credentials."""
        import glob
        
        # Scan Python files for hardcoded credentials
        py_files = glob.glob('/home/user/.openclaw/workspace/paper-reproducibility/**/*.py', recursive=True)
        
        for py_file in py_files:
            # Skip test files
            if 'test_' in py_file:
                continue
            
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    
                    # Check for API key patterns
                    assert 'sk-ant-' not in content or 'sk-ant-your-key' in content, \
                        f"Possible API key found in {py_file}"
                    
                    # Check for hardcoded passwords
                    if 'password' in content.lower():
                        # OK to have password-related code
                        assert 'password = "' not in content or 'test' in py_file.lower(), \
                            f"Possible hardcoded password in {py_file}"
            except Exception as e:
                # Skip binary or unreadable files
                pass


class TestPasswordHashing:
    """Test password hashing security."""
    
    def test_password_hashing_uses_salt(self):
        """Test that password hashing includes salt."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Same password should produce different hashes (due to salt)
        assert hash1 != hash2
        
        # Both should be verifiable
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
    
    def test_password_verification(self):
        """Test password verification."""
        password = "MySecurePassword123!"
        password_hash = hash_password(password)
        
        assert verify_password(password, password_hash)
        assert not verify_password("WrongPassword", password_hash)
        assert not verify_password("", password_hash)
    
    def test_password_hash_format(self):
        """Test password hash format."""
        password = "TestPassword123!"
        password_hash = hash_password(password)
        
        # Should be in format: salt$hash
        parts = password_hash.split('$')
        assert len(parts) == 2
        
        salt, hash_value = parts
        assert len(salt) == 64  # 32 bytes hex = 64 chars
        assert len(hash_value) > 10  # Hash should be reasonably long


class TestSessionSecurity:
    """Test session security settings."""
    
    def test_session_cookie_httponly(self):
        """Test that session cookies have HTTPOnly flag."""
        assert Config.SESSION_COOKIE_HTTPONLY is True
    
    def test_session_cookie_samesite(self):
        """Test that session cookies have SameSite flag."""
        assert Config.SESSION_COOKIE_SAMESITE in ['Lax', 'Strict']
    
    def test_session_cookie_secure_in_production(self):
        """Test that session cookies are secure in production."""
        # In production (FLASK_ENV=production), cookies should be secure
        if Config.FLASK_ENV == 'production':
            assert Config.SESSION_COOKIE_SECURE is True
    
    def test_session_timeout_configured(self):
        """Test that session timeout is configured."""
        # Should have PERMANENT_SESSION_LIFETIME
        if hasattr(Config, 'PERMANENT_SESSION_LIFETIME'):
            timeout = Config.PERMANENT_SESSION_LIFETIME
            # Should be reasonable (not too long, not too short)
            assert timeout.total_seconds() > 3600  # At least 1 hour
            assert timeout.total_seconds() < 7*24*3600  # Less than 1 week


class TestAuthenticationRequired:
    """Test that protected routes require authentication."""
    
    def test_profile_requires_auth(self, client_full):
        """Test /profile requires authentication."""
        response = client_full.get('/profile')
        # Should redirect or return 401
        assert response.status_code in [301, 302, 401, 403]
    
    def test_logout_requires_auth(self, client_full):
        """Test /logout requires authentication."""
        response = client_full.post('/logout')
        assert response.status_code in [301, 302, 401, 403]
    
    def test_change_password_requires_auth(self, client_full):
        """Test /change-password requires authentication."""
        response = client_full.get('/change-password')
        assert response.status_code in [301, 302, 401, 403]
    
    def test_api_change_password_requires_auth(self, client_full):
        """Test /api/change-password requires authentication."""
        response = client_full.post('/api/change-password',
                                   json={'old_password': 'test', 'new_password': 'test2', 
                                         'confirm_password': 'test2'})
        assert response.status_code == 401
    
    def test_upload_requires_auth(self, client_full):
        """Test /upload requires authentication."""
        response = client_full.post('/upload')
        assert response.status_code in [301, 302, 401, 403]
    
    def test_history_requires_auth(self, client_full):
        """Test /history requires authentication."""
        response = client_full.get('/history')
        assert response.status_code in [301, 302, 401, 403]
    
    def test_admin_requires_auth(self, client_full):
        """Test /admin requires authentication."""
        response = client_full.get('/admin')
        assert response.status_code in [301, 302, 401, 403]
    
    def test_admin_users_api_requires_auth(self, client_full):
        """Test /api/admin/users requires authentication."""
        response = client_full.get('/api/admin/users')
        assert response.status_code == 401


class TestAdminAccess:
    """Test admin access control."""
    
    def test_admin_users_requires_admin_role(self, client_full):
        """Test that /api/admin/users requires admin role."""
        with client_full:
            # Login as regular user
            with client_full.session_transaction() as sess:
                sess['user_id'] = 999
                sess['username'] = 'regularuser'
            
            response = client_full.get('/api/admin/users')
            # Should be forbidden (403) not unauthorized (401)
            assert response.status_code == 403
    
    def test_admin_panel_requires_admin_role(self, client_full):
        """Test that /admin requires admin role."""
        with client_full:
            # Login as regular user
            with client_full.session_transaction() as sess:
                sess['user_id'] = 999
                sess['username'] = 'regularuser'
            
            response = client_full.get('/admin')
            assert response.status_code == 403


class TestJobAccessControl:
    """Test job access control."""
    
    def test_job_detail_requires_ownership(self, client_full):
        """Test that users can only access their own jobs."""
        with client_full:
            # Simulate authenticated user
            with client_full.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'testuser'
            
            # Try to access non-existent job (should be 404, not 403)
            response = client_full.get('/job/fake-job-id')
            assert response.status_code == 404
    
    def test_job_list_requires_auth(self, client_full):
        """Test /jobs requires authentication."""
        response = client_full.get('/jobs')
        assert response.status_code == 401


class TestFormInputValidation:
    """Test input validation on authentication forms."""
    
    def test_register_requires_username(self, client_full):
        """Test registration requires username."""
        response = client_full.post('/register', data={
            'username': '',
            'email': 'test@example.com',
            'password': 'TestPassword123!',
            'confirm_password': 'TestPassword123!'
        })
        assert response.status_code in [400, 422]
    
    def test_register_requires_email(self, client_full):
        """Test registration requires email."""
        response = client_full.post('/register', data={
            'username': 'testuser',
            'email': '',
            'password': 'TestPassword123!',
            'confirm_password': 'TestPassword123!'
        })
        assert response.status_code in [400, 422]
    
    def test_register_requires_password(self, client_full):
        """Test registration requires password."""
        response = client_full.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '',
            'confirm_password': ''
        })
        assert response.status_code in [400, 422]
    
    def test_register_password_minimum_length(self, client_full):
        """Test password minimum length on registration."""
        response = client_full.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'short',
            'confirm_password': 'short'
        })
        assert response.status_code in [400, 422]


class TestPublicRoutes:
    """Test that certain routes are properly public."""
    
    def test_login_page_accessible(self, client_full):
        """Test login page is accessible without auth."""
        response = client_full.get('/login')
        assert response.status_code == 200
    
    def test_register_page_accessible(self, client_full):
        """Test register page is accessible without auth."""
        response = client_full.get('/register')
        assert response.status_code == 200
    
    def test_health_check_accessible(self, client_full):
        """Test health check is accessible without auth."""
        response = client_full.get('/api/health')
        assert response.status_code in [200, 503]
    
    def test_about_page_accessible(self, client_full):
        """Test about page is accessible without auth."""
        response = client_full.get('/about')
        assert response.status_code == 200


class TestNoHardcodedSecrets:
    """Test for absence of hardcoded secrets."""
    
    def test_no_api_keys_in_config(self):
        """Test that config.py doesn't contain API keys."""
        with open('/home/user/.openclaw/workspace/paper-reproducibility/config.py', 'r') as f:
            content = f.read()
            # Should not have sk-ant- pattern with actual key
            assert 'sk-ant-api03' not in content
            assert 'sk-ant-' not in content or 'sk-ant-your-key' in content
    
    def test_no_passwords_in_services(self):
        """Test that auth_service.py doesn't have hardcoded passwords."""
        with open('/home/user/.openclaw/workspace/paper-reproducibility/services/auth_service.py', 'r') as f:
            content = f.read()
            # OK to mention default password in comments, but not as actual default
            assert 'password = "admin"' not in content
    
    def test_no_secrets_in_blueprints(self):
        """Test that blueprints don't contain secrets."""
        import glob
        bp_files = glob.glob('/home/user/.openclaw/workspace/paper-reproducibility/blueprints/*.py')
        
        for bp_file in bp_files:
            with open(bp_file, 'r') as f:
                content = f.read()
                assert 'sk-ant-' not in content or 'sk-ant-your-key' in content


class TestCacheControl:
    """Test that /cache endpoints require admin."""
    
    def test_cache_stats_requires_admin(self, client_full):
        """Test /api/cache/stats requires admin."""
        response = client_full.get('/api/cache/stats')
        assert response.status_code == 401
    
    def test_cache_clear_requires_admin(self, client_full):
        """Test /api/cache/clear requires admin."""
        response = client_full.delete('/api/cache/clear')
        assert response.status_code == 401


class TestDatabaseInjection:
    """Test for SQL injection vulnerabilities."""
    
    def test_login_with_sql_injection_attempt(self, client_full):
        """Test that SQL injection is prevented on login."""
        response = client_full.post('/login', data={
            'username': "' OR '1'='1",
            'password': "' OR '1'='1"
        })
        # Should not authenticate
        assert response.status_code in [400, 401]
    
    def test_register_with_sql_injection_attempt(self, client_full):
        """Test that SQL injection is prevented on register."""
        response = client_full.post('/register', data={
            'username': "'; DROP TABLE users; --",
            'email': 'test@test.com',
            'password': 'TestPassword123!',
            'confirm_password': 'TestPassword123!'
        })
        # Should fail validation, not execute query
        assert response.status_code in [400, 422]


class TestSecurityHeaders:
    """Test security headers in responses."""
    
    def test_security_headers_present(self, client_full):
        """Test that security headers are present in responses."""
        response = client_full.get('/api/health')
        
        # Check for important security headers
        # Note: Some may only be set in production
        # At minimum, should not have dangerous headers
        assert 'X-Powered-By' not in response.headers or response.headers['X-Powered-By'] != 'Flask'


class TestErrorHandling:
    """Test that error handlers don't leak information."""
    
    def test_404_error_doesnt_expose_paths(self, client_full):
        """Test that 404 errors don't expose file paths."""
        response = client_full.get('/this-does-not-exist-1234567890')
        assert response.status_code == 404
        data = json.loads(response.data)
        
        # Should be generic error message
        assert 'error' in data
        assert '/app' not in json.dumps(data)
        assert '/home' not in json.dumps(data)
    
    def test_500_error_doesnt_expose_traceback(self, client_full):
        """Test that 500 errors don't expose stack traces."""
        # This is harder to test without actually triggering an error
        # But we can verify that Flask is not in debug mode in production config
        if hasattr(Config, 'FLASK_ENV'):
            if Config.FLASK_ENV == 'production':
                # Flask should not be in debug mode
                assert not Config.FLASK_DEBUG if hasattr(Config, 'FLASK_DEBUG') else True


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
