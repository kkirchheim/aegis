"""Integration tests for admin management endpoints"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api, pytest.mark.admin]


class TestAdminUserList:
    """Test listing users"""
    
    def test_admin_list_users(self, admin_user):
        """Test admin can list all users"""
        response = admin_user.get('/api/admin/users')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)
        assert len(data["users"]) >= 1
    
    def test_list_users_non_admin(self, authenticated_user):
        """Test non-admin can't list users"""
        response = authenticated_user.get('/api/admin/users')
        
        assert response.status_code == 403
    
    def test_list_users_unauthenticated(self, client):
        """Test unauthenticated can't list users"""
        response = client.get('/api/admin/users')
        
        assert response.status_code == 401


class TestAdminUserStatus:
    """Test updating user status (activate/deactivate)"""
    
    def test_activate_user(self, admin_user, inactive_user):
        """Test activating an inactive user"""
        response = admin_user.patch(f'/api/admin/users/{inactive_user["id"]}', json={
            "is_active": True
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        
        # Verify user is now active
        users_data = admin_user.get('/api/admin/users').get_json()
        activated = [u for u in users_data["users"] if u["id"] == inactive_user["id"]][0]
        assert activated["is_active"] is True
    
    def test_deactivate_user(self, admin_user, active_user):
        """Test deactivating an active user"""
        response = admin_user.patch(f'/api/admin/users/{active_user["id"]}', json={
            "is_active": False
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
    
    def test_update_missing_is_active_field(self, admin_user, active_user):
        """Test PATCH without is_active field"""
        response = admin_user.patch(f'/api/admin/users/{active_user["id"]}', json={})

        assert response.status_code in (400, 422)
    
    def test_update_nonexistent_user(self, admin_user):
        """Test updating non-existent user"""
        response = admin_user.patch('/api/admin/users/99999', json={
            "is_active": True
        })
        
        assert response.status_code == 404
    
    def test_update_user_non_admin(self, authenticated_user, inactive_user):
        """Test non-admin can't update user status"""
        response = authenticated_user.patch(f'/api/admin/users/{inactive_user["id"]}', json={
            "is_active": True
        })
        
        assert response.status_code == 403


class TestAdminUserDelete:
    """Test deleting users"""
    
    def test_delete_user_success(self, admin_user, test_user):
        """Test deleting a user"""
        user_id = test_user["id"]
        
        response = admin_user.delete(f'/api/admin/users/{user_id}')
        
        assert response.status_code == 204  # No content
        
        # Verify user is deleted
        response = admin_user.get('/api/admin/users')
        users_data = response.get_json()
        user_ids = [u["id"] for u in users_data["users"]]
        assert user_id not in user_ids
    
    def test_delete_nonexistent_user(self, admin_user):
        """Test deleting non-existent user"""
        response = admin_user.delete('/api/admin/users/99999')
        
        assert response.status_code == 404
    
    def test_delete_own_account(self, admin_user, app):
        """Test admin can't delete their own account"""
        # Get the admin user ID from session
        with admin_user.session_transaction() as sess:
            admin_id = sess.get('user_id')
        
        response = admin_user.delete(f'/api/admin/users/{admin_id}')
        
        assert response.status_code == 400  # Can't delete self
    
    def test_delete_user_non_admin(self, authenticated_user, test_user):
        """Test non-admin can't delete users"""
        response = authenticated_user.delete(f'/api/admin/users/{test_user["id"]}')
        
        assert response.status_code == 403
    
    def test_delete_requires_auth(self, client, test_user):
        """Test delete requires authentication"""
        response = client.delete(f'/api/admin/users/{test_user["id"]}')
        
        assert response.status_code == 401


class TestAdminPanelPage:
    """Test admin panel page"""
    
    def test_admin_panel_page_admin(self, admin_user):
        """Test admin can access admin panel"""
        response = admin_user.get('/admin')
        
        assert response.status_code == 200
    
    def test_admin_panel_page_non_admin(self, authenticated_user):
        """Test non-admin can't access admin panel"""
        response = authenticated_user.get('/admin')
        
        assert response.status_code == 403
    
    def test_admin_panel_page_unauthenticated(self, client):
        """Test unauthenticated can't access admin panel"""
        response = client.get('/admin')
        
        assert response.status_code in [302, 401]  # Redirect or forbidden
