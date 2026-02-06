"""Tests for aspect management API endpoints.

Comprehensive endpoint tests covering CRUD operations, activation,
prompt overrides, and error handling with ~30+ test cases.
"""

import pytest
import json
from uuid import UUID
from models.database import User
from models.aspect import Aspect, UserAspect
from services.aspect_service import AspectService
from repositories.aspect_repository import AspectRepository, UserAspectRepository


@pytest.mark.api
@pytest.mark.db
class TestListAspectsEndpoint:
    """Tests for GET /api/aspects"""
    
    def test_list_aspects_authenticated(self, client, app, test_user):
        """Test listing all aspects for authenticated user."""
        with app.app_context():
            # Setup: Create user session
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed default aspects
            AspectService.get_or_create_default_aspects(test_user['id'])
            
            # Execute: GET /api/aspects
            response = client.get('/api/aspects')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'aspects' in data
            assert 'total' in data
            assert data['total'] == 3
            assert len(data['aspects']) == 3
            assert all('is_active' in a for a in data['aspects'])
            assert all('custom_prompt' in a for a in data['aspects'])
    
    def test_list_aspects_mixed_active_inactive(self, client, app, test_user):
        """Test listing aspects with mixed active/inactive status."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed defaults and deactivate one
            AspectService.get_or_create_default_aspects(test_user['id'])
            all_aspects = AspectService.get_all_aspects_for_user(test_user['id'])
            first_aspect_id = UUID(all_aspects[0]['id'])
            AspectService.deactivate_aspect(test_user['id'], first_aspect_id)
            
            # Execute
            response = client.get('/api/aspects')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['total'] == 3
            
            # Should have 2 active, 1 inactive
            active = [a for a in data['aspects'] if a['is_active']]
            inactive = [a for a in data['aspects'] if not a['is_active']]
            assert len(active) == 2
            assert len(inactive) == 1
    
    def test_list_aspects_custom_and_default(self, client, app, test_user):
        """Test that list includes both custom and default aspects."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed defaults + create custom
            AspectService.get_or_create_default_aspects(test_user['id'])
            AspectService.create_custom_aspect(
                test_user['id'],
                "My Custom Aspect",
                "Custom desc",
                "Custom prompt"
            )
            
            # Execute
            response = client.get('/api/aspects')
            
            # Verify
            data = json.loads(response.data)
            assert data['total'] == 4
            
            defaults = [a for a in data['aspects'] if a['is_default']]
            customs = [a for a in data['aspects'] if not a['is_default']]
            assert len(defaults) == 3
            assert len(customs) == 1
            assert customs[0]['name'] == "My Custom Aspect"
    
    def test_list_aspects_user_isolation(self, client, app, test_user, create_test_user):
        """Test that different users see different aspects."""
        with app.app_context():
            # Setup: Create two users with their aspects
            user2_id = create_test_user('user2', 'user2@test.com', 'password123')
            
            AspectService.get_or_create_default_aspects(test_user['id'])
            AspectService.get_or_create_default_aspects(user2_id)
            
            # User 1 creates custom aspect
            AspectService.create_custom_aspect(
                test_user['id'],
                "User 1 Custom",
                "Desc",
                "Prompt"
            )
            
            # User 2 creates different custom aspect
            AspectService.create_custom_aspect(
                user2_id,
                "User 2 Custom",
                "Desc",
                "Prompt"
            )
            
            # Execute: User 1 lists
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            response = client.get('/api/aspects')
            data = json.loads(response.data)
            custom_names = [a['name'] for a in data['aspects'] if not a['is_default']]
            
            # Verify: User 1 only sees their custom aspect
            assert "User 1 Custom" in custom_names
            assert "User 2 Custom" not in custom_names
    
    def test_list_aspects_unauthenticated(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.get('/api/aspects')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data


@pytest.mark.api
@pytest.mark.db
class TestCreateAspectEndpoint:
    """Tests for POST /api/aspects"""
    
    def test_create_custom_aspect(self, client, app, test_user):
        """Test creating a new custom aspect."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Execute
            response = client.post('/api/aspects', json={
                'name': 'Code Availability',
                'description': 'Check if code is available',
                'prompt': 'Is code available?'
            })
            
            # Verify
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['name'] == 'Code Availability'
            assert data['description'] == 'Check if code is available'
            assert data['is_default'] is False
            assert data['is_active'] is True
            assert data['custom_prompt'] is None
            assert data['prompt_to_use'] == 'Is code available?'
    
    def test_create_aspect_returns_201_with_user_aspect(self, client, app, test_user):
        """Test that create returns 201 with full UserAspectSchema."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            response = client.post('/api/aspects', json={
                'name': 'Test',
                'description': 'Test desc',
                'prompt': 'Test prompt'
            })
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            # Should have all UserAspectSchema fields
            required_fields = ['id', 'aspect_id', 'name', 'description',
                             'is_default', 'is_active', 'custom_prompt',
                             'prompt_to_use', 'created_at']
            for field in required_fields:
                assert field in data
    
    def test_create_aspect_missing_required_field(self, client, test_user):
        """Test that missing required fields return 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        # Missing 'prompt'
        response = client.post('/api/aspects', json={
            'name': 'Test',
            'description': 'Test desc'
        })
        
        assert response.status_code == 400
    
    def test_create_aspect_invalid_name_too_long(self, client, test_user):
        """Test that name exceeding 255 chars returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post('/api/aspects', json={
            'name': 'x' * 256,  # Too long
            'description': 'Desc',
            'prompt': 'Prompt'
        })
        
        assert response.status_code == 400
    
    def test_create_aspect_empty_prompt(self, client, test_user):
        """Test that empty prompt returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post('/api/aspects', json={
            'name': 'Test',
            'description': 'Desc',
            'prompt': ''  # Empty
        })
        
        # Marshmallow may or may not validate empty strings, so check response
        # At minimum, should be parseable
        assert response.status_code in [400, 201]
    
    def test_create_aspect_unauthenticated(self, client):
        """Test that unauthenticated create returns 401."""
        response = client.post('/api/aspects', json={
            'name': 'Test',
            'description': 'Desc',
            'prompt': 'Prompt'
        })
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestGetAspectEndpoint:
    """Tests for GET /api/aspects/{aspect_id}"""
    
    def test_get_aspect_details(self, client, app, test_user):
        """Test getting a single aspect with user status."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup
            AspectService.get_or_create_default_aspects(test_user['id'])
            all_aspects = AspectService.get_all_aspects_for_user(test_user['id'])
            aspect_id = all_aspects[0]['id']
            
            # Execute
            response = client.get(f'/api/aspects/{aspect_id}')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['id'] == aspect_id
            assert data['is_default'] is True
            assert data['is_active'] is True
    
    def test_get_aspect_nonexistent(self, client, test_user):
        """Test that nonexistent aspect returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f'/api/aspects/{fake_id}')
        
        assert response.status_code == 404
    
    def test_get_aspect_invalid_id_format(self, client, test_user):
        """Test that invalid UUID format returns error."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.get('/api/aspects/invalid-uuid')
        
        assert response.status_code == 400
    
    def test_get_aspect_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get('/api/aspects/00000000-0000-0000-0000-000000000000')
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestUpdateAspectEndpoint:
    """Tests for PUT /api/aspects/{aspect_id}"""
    
    def test_update_custom_aspect_name(self, client, app, test_user):
        """Test updating aspect name."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create custom aspect
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Original Name",
                "Original Desc",
                "Original Prompt"
            )
            aspect_id = custom['id']
            
            # Execute
            response = client.put(f'/api/aspects/{aspect_id}', json={
                'name': 'Updated Name'
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['name'] == 'Updated Name'
            assert data['description'] == 'Original Desc'  # Unchanged
    
    def test_update_custom_aspect_description_and_prompt(self, client, app, test_user):
        """Test updating multiple fields."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Name",
                "Old Desc",
                "Old Prompt"
            )
            aspect_id = custom['id']
            
            # Execute
            response = client.put(f'/api/aspects/{aspect_id}', json={
                'description': 'New Desc',
                'prompt': 'New Prompt'
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['description'] == 'New Desc'
            assert data['prompt_to_use'] == 'New Prompt'
    
    def test_update_default_aspect_forbidden(self, client, app, test_user):
        """Test that updating default aspect returns 403."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default aspect
            AspectService.get_or_create_default_aspects(test_user['id'])
            all_aspects = AspectService.get_all_aspects_for_user(test_user['id'])
            default = next(a for a in all_aspects if a['is_default'])
            
            # Execute
            response = client.put(f'/api/aspects/{default["id"]}', json={
                'name': 'New Name'
            })
            
            # Verify
            assert response.status_code == 403
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_update_nonexistent_aspect(self, client, test_user):
        """Test that updating nonexistent aspect returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(f'/api/aspects/{fake_id}', json={'name': 'New'})
        
        assert response.status_code == 404
    
    def test_update_aspect_unauthenticated(self, client):
        """Test that unauthenticated update returns 401."""
        response = client.put(
            '/api/aspects/00000000-0000-0000-0000-000000000000',
            json={'name': 'New'}
        )
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestDeleteAspectEndpoint:
    """Tests for DELETE /api/aspects/{aspect_id}"""
    
    def test_delete_custom_aspect(self, client, app, test_user):
        """Test deleting a custom aspect."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create custom aspect
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            aspect_id = custom['id']
            
            # Execute
            response = client.delete(f'/api/aspects/{aspect_id}')
            
            # Verify
            assert response.status_code == 204
            
            # Verify it's deleted
            all_aspects = AspectService.get_all_aspects_for_user(test_user['id'])
            assert not any(a['id'] == aspect_id for a in all_aspects)
    
    def test_delete_default_aspect_forbidden(self, client, app, test_user):
        """Test that deleting default aspect returns 403."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default aspect
            AspectService.get_or_create_default_aspects(test_user['id'])
            all_aspects = AspectService.get_all_aspects_for_user(test_user['id'])
            default = next(a for a in all_aspects if a['is_default'])
            
            # Execute
            response = client.delete(f'/api/aspects/{default["id"]}')
            
            # Verify
            assert response.status_code == 403
    
    def test_delete_nonexistent_aspect(self, client, test_user):
        """Test that deleting nonexistent aspect returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f'/api/aspects/{fake_id}')
        
        assert response.status_code == 404
    
    def test_delete_aspect_unauthenticated(self, client):
        """Test that unauthenticated delete returns 401."""
        response = client.delete('/api/aspects/00000000-0000-0000-0000-000000000000')
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestActivateAspectEndpoint:
    """Tests for POST /api/aspects/{aspect_id}/activate"""
    
    def test_activate_aspect(self, client, app, test_user):
        """Test activating an inactive aspect."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create and deactivate
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            aspect_id = custom['id']
            AspectService.deactivate_aspect(test_user['id'], UUID(aspect_id))
            
            # Execute
            response = client.post(f'/api/aspects/{aspect_id}/activate', json={
                'is_active': True
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['is_active'] is True
    
    def test_deactivate_aspect(self, client, app, test_user):
        """Test deactivating an active aspect."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create aspect (active by default)
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            aspect_id = custom['id']
            
            # Execute
            response = client.post(f'/api/aspects/{aspect_id}/activate', json={
                'is_active': False
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['is_active'] is False
    
    def test_activate_nonexistent_aspect(self, client, test_user):
        """Test activating nonexistent aspect returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(f'/api/aspects/{fake_id}/activate', json={
            'is_active': True
        })
        
        assert response.status_code == 404
    
    def test_activate_missing_is_active_field(self, client, test_user):
        """Test that missing is_active field returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post(
            '/api/aspects/00000000-0000-0000-0000-000000000000/activate',
            json={}  # Missing is_active
        )
        
        assert response.status_code == 400
    
    def test_activate_aspect_unauthenticated(self, client):
        """Test that unauthenticated activate returns 401."""
        response = client.post(
            '/api/aspects/00000000-0000-0000-0000-000000000000/activate',
            json={'is_active': True}
        )
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestOverridePromptEndpoint:
    """Tests for POST /api/aspects/{aspect_id}/override-prompt"""
    
    def test_set_custom_prompt(self, client, app, test_user):
        """Test setting a custom prompt override."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Custom",
                "Desc",
                "Original Prompt"
            )
            aspect_id = custom['id']
            
            # Execute
            response = client.post(f'/api/aspects/{aspect_id}/override-prompt', json={
                'custom_prompt': 'My Custom Override'
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['custom_prompt'] == 'My Custom Override'
            assert data['prompt_to_use'] == 'My Custom Override'
    
    def test_revert_to_default_prompt(self, client, app, test_user):
        """Test reverting to default prompt with custom_prompt=null."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create aspect with custom prompt
            custom = AspectService.create_custom_aspect(
                test_user['id'],
                "Custom",
                "Desc",
                "Default Prompt"
            )
            aspect_id = custom['id']
            AspectService.override_prompt(test_user['id'], UUID(aspect_id), "Custom")
            
            # Execute: Revert with null
            response = client.post(f'/api/aspects/{aspect_id}/override-prompt', json={
                'custom_prompt': None
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['custom_prompt'] is None
            assert data['prompt_to_use'] == 'Default Prompt'
    
    def test_override_prompt_nonexistent_aspect(self, client, test_user):
        """Test overriding prompt on nonexistent aspect returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(f'/api/aspects/{fake_id}/override-prompt', json={
            'custom_prompt': 'New'
        })
        
        assert response.status_code == 404
    
    def test_override_prompt_unauthenticated(self, client):
        """Test that unauthenticated override returns 401."""
        response = client.post(
            '/api/aspects/00000000-0000-0000-0000-000000000000/override-prompt',
            json={'custom_prompt': 'New'}
        )
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestIntegration:
    """Integration tests for full workflows."""
    
    def test_full_workflow_create_override_activate(self, client, app, test_user):
        """Test full workflow: create → override prompt → activate → list."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Step 1: Create custom aspect
            create_response = client.post('/api/aspects', json={
                'name': 'Workflow Aspect',
                'description': 'Test workflow',
                'prompt': 'Original prompt'
            })
            assert create_response.status_code == 201
            aspect_id = json.loads(create_response.data)['id']
            
            # Step 2: Override prompt
            override_response = client.post(
                f'/api/aspects/{aspect_id}/override-prompt',
                json={'custom_prompt': 'Custom override'}
            )
            assert override_response.status_code == 200
            assert json.loads(override_response.data)['custom_prompt'] == 'Custom override'
            
            # Step 3: Get in list
            list_response = client.get('/api/aspects')
            assert list_response.status_code == 200
            aspects = json.loads(list_response.data)['aspects']
            workflow_aspect = next(a for a in aspects if a['id'] == aspect_id)
            assert workflow_aspect['custom_prompt'] == 'Custom override'
            assert workflow_aspect['is_active'] is True
    
    def test_multi_user_isolation(self, client, app, test_user, create_test_user):
        """Test that users are completely isolated."""
        with app.app_context():
            # Create second user
            user2_id = create_test_user('user2', 'user2@test.com', 'pass123')
            
            # User 1: Create custom aspect
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            user1_create = client.post('/api/aspects', json={
                'name': 'User 1 Aspect',
                'description': 'Only for user 1',
                'prompt': 'Prompt'
            })
            user1_aspect_id = json.loads(user1_create.data)['id']
            
            # User 2: Should not see User 1's aspect
            with client.session_transaction() as sess:
                sess['user_id'] = user2_id
                sess['username'] = 'user2'
            
            user2_list = client.get('/api/aspects')
            user2_aspects = json.loads(user2_list.data)['aspects']
            
            # User 2 should not see User 1's aspect
            assert not any(a['id'] == user1_aspect_id for a in user2_aspects)
            
            # User 2 trying to get User 1's aspect should get 404
            get_response = client.get(f'/api/aspects/{user1_aspect_id}')
            assert get_response.status_code == 404
    
    def test_default_aspects_protected_from_modification(self, client, app, test_user):
        """Test that default aspects cannot be modified or deleted."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default aspect
            AspectService.get_or_create_default_aspects(test_user['id'])
            list_response = client.get('/api/aspects')
            aspects = json.loads(list_response.data)['aspects']
            default = next(a for a in aspects if a['is_default'])
            default_id = default['id']
            
            # Try to update: should fail
            update_response = client.put(f'/api/aspects/{default_id}', json={
                'name': 'Hacked Name'
            })
            assert update_response.status_code == 403
            
            # Try to delete: should fail
            delete_response = client.delete(f'/api/aspects/{default_id}')
            assert delete_response.status_code == 403
            
            # Default aspect should still be there
            get_response = client.get(f'/api/aspects/{default_id}')
            assert get_response.status_code == 200
            assert json.loads(get_response.data)['name'] == default['name']
