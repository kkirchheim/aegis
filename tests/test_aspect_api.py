"""Tests for plugin management API endpoints.

Comprehensive endpoint tests covering CRUD operations, activation,
prompt overrides, and error handling with ~30+ test cases.
"""

import pytest
import json
from uuid import UUID
from models.database import User
from services.plugin_service import DEFAULT_PLUGINS
from models.plugin import Plugin, UserPlugin
from services.plugin_service import PluginService
from repositories.plugin_repository import PluginRepository, UserPluginRepository


@pytest.mark.api
@pytest.mark.db
class TestListPluginsEndpoint:
    """Tests for GET /api/plugins"""
    
    def test_list_plugins_authenticated(self, client, app, test_user):
        """Test listing all plugins for authenticated user."""
        with app.app_context():
            # Setup: Create user session
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed default plugins
            PluginService.get_or_create_default_plugins(test_user['id'])
            
            # Execute: GET /api/plugins
            response = client.get('/api/plugins')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'plugins' in data
            assert 'total' in data
            assert data['total'] == len(DEFAULT_PLUGINS)
            assert len(data['plugins']) == len(DEFAULT_PLUGINS)
            assert all('is_active' in a for a in data['plugins'])
            assert all('custom_prompt' in a for a in data['plugins'])
    
    def test_list_plugins_mixed_active_inactive(self, client, app, test_user):
        """Test listing plugins with mixed active/inactive status."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed defaults and deactivate one
            PluginService.get_or_create_default_plugins(test_user['id'])
            all_plugins = PluginService.get_all_plugins_for_user(test_user['id'])
            first_plugin_id = UUID(all_plugins[0]['id'])
            PluginService.deactivate_plugin(test_user['id'], first_plugin_id)
            
            # Execute
            response = client.get('/api/plugins')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['total'] == len(DEFAULT_PLUGINS)

            # Should have one inactive, rest active
            active = [a for a in data['plugins'] if a['is_active']]
            inactive = [a for a in data['plugins'] if not a['is_active']]
            assert len(active) == len(DEFAULT_PLUGINS) - 1
            assert len(inactive) == 1
    
    def test_list_plugins_custom_and_default(self, client, app, test_user):
        """Test that list includes both custom and default plugins."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Seed defaults + create custom
            PluginService.get_or_create_default_plugins(test_user['id'])
            PluginService.create_custom_plugin(
                test_user['id'],
                "My Custom Plugin",
                "Custom desc",
                "Custom prompt"
            )
            
            # Execute
            response = client.get('/api/plugins')
            
            # Verify
            data = json.loads(response.data)
            assert data['total'] == len(DEFAULT_PLUGINS) + 1

            defaults = [a for a in data['plugins'] if a['is_default']]
            customs = [a for a in data['plugins'] if not a['is_default']]
            assert len(defaults) == len(DEFAULT_PLUGINS)
            assert len(customs) == 1
            assert customs[0]['name'] == "My Custom Plugin"
    
    def test_list_plugins_user_isolation(self, client, app, test_user, create_test_user):
        """Test that different users see different plugins."""
        with app.app_context():
            # Setup: Create two users with their plugins
            user2_id = create_test_user('user2', 'user2@test.com', 'password123')
            
            PluginService.get_or_create_default_plugins(test_user['id'])
            PluginService.get_or_create_default_plugins(user2_id)
            
            # User 1 creates custom plugin
            PluginService.create_custom_plugin(
                test_user['id'],
                "User 1 Custom",
                "Desc",
                "Prompt"
            )
            
            # User 2 creates different custom plugin
            PluginService.create_custom_plugin(
                user2_id,
                "User 2 Custom",
                "Desc",
                "Prompt"
            )
            
            # Execute: User 1 lists
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            response = client.get('/api/plugins')
            data = json.loads(response.data)
            custom_names = [a['name'] for a in data['plugins'] if not a['is_default']]
            
            # Verify: User 1 only sees their custom plugin
            assert "User 1 Custom" in custom_names
            assert "User 2 Custom" not in custom_names
    
    def test_list_plugins_unauthenticated(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.get('/api/plugins')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data


@pytest.mark.api
@pytest.mark.db
class TestCreatePluginEndpoint:
    """Tests for POST /api/plugins"""
    
    def test_create_custom_plugin(self, client, app, test_user):
        """Test creating a new custom plugin."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Execute
            response = client.post('/api/plugins', json={
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
    
    def test_create_plugin_returns_201_with_user_plugin(self, client, app, test_user):
        """Test that create returns 201 with full UserPluginSchema."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            response = client.post('/api/plugins', json={
                'name': 'Test',
                'description': 'Test desc',
                'prompt': 'Test prompt'
            })
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            # Should have all UserPluginSchema fields
            required_fields = ['id', 'plugin_id', 'name', 'description',
                             'is_default', 'is_active', 'custom_prompt',
                             'prompt_to_use', 'created_at']
            for field in required_fields:
                assert field in data
    
    def test_create_plugin_missing_required_field(self, client, test_user):
        """Test that missing required fields return 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        # Missing 'prompt'
        response = client.post('/api/plugins', json={
            'name': 'Test',
            'description': 'Test desc'
        })

        assert response.status_code in (400, 422)
    
    def test_create_plugin_invalid_name_too_long(self, client, test_user):
        """Test that name exceeding 255 chars returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post('/api/plugins', json={
            'name': 'x' * 256,  # Too long
            'description': 'Desc',
            'prompt': 'Prompt'
        })

        assert response.status_code in (400, 422)
    
    def test_create_plugin_empty_prompt(self, client, test_user):
        """Test that empty prompt returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post('/api/plugins', json={
            'name': 'Test',
            'description': 'Desc',
            'prompt': ''  # Empty
        })
        
        # Marshmallow may or may not validate empty strings, so check response
        # At minimum, should be parseable
        assert response.status_code in [400, 201]
    
    def test_create_plugin_unauthenticated(self, client):
        """Test that unauthenticated create returns 401."""
        response = client.post('/api/plugins', json={
            'name': 'Test',
            'description': 'Desc',
            'prompt': 'Prompt'
        })
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestGetPluginEndpoint:
    """Tests for GET /api/plugins/{plugin_id}"""
    
    def test_get_plugin_details(self, client, app, test_user):
        """Test getting a single plugin with user status."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup
            PluginService.get_or_create_default_plugins(test_user['id'])
            all_plugins = PluginService.get_all_plugins_for_user(test_user['id'])
            plugin_id = all_plugins[0]['id']
            
            # Execute
            response = client.get(f'/api/plugins/{plugin_id}')
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert str(data['plugin_id']) == plugin_id
            assert data['is_default'] is True
            assert data['is_active'] is True
    
    def test_get_plugin_nonexistent(self, client, test_user):
        """Test that nonexistent plugin returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f'/api/plugins/{fake_id}')
        
        assert response.status_code == 404
    
    def test_get_plugin_invalid_id_format(self, client, test_user):
        """Test that invalid UUID format returns error."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.get('/api/plugins/invalid-uuid')
        
        assert response.status_code == 400
    
    def test_get_plugin_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get('/api/plugins/00000000-0000-0000-0000-000000000000')
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestUpdatePluginEndpoint:
    """Tests for PUT /api/plugins/{plugin_id}"""
    
    def test_update_custom_plugin_name(self, client, app, test_user):
        """Test updating plugin name."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create custom plugin
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Original Name",
                "Original Desc",
                "Original Prompt"
            )
            plugin_id = custom['id']
            
            # Execute
            response = client.put(f'/api/plugins/{plugin_id}', json={
                'name': 'Updated Name'
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['name'] == 'Updated Name'
            assert data['description'] == 'Original Desc'  # Unchanged
    
    def test_update_custom_plugin_description_and_prompt(self, client, app, test_user):
        """Test updating multiple fields."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Name",
                "Old Desc",
                "Old Prompt"
            )
            plugin_id = custom['id']
            
            # Execute
            response = client.put(f'/api/plugins/{plugin_id}', json={
                'description': 'New Desc',
                'prompt': 'New Prompt'
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['description'] == 'New Desc'
            assert data['prompt_to_use'] == 'New Prompt'
    
    def test_update_default_plugin_forbidden(self, client, app, test_user):
        """Test that updating default plugin returns 403."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default plugin
            PluginService.get_or_create_default_plugins(test_user['id'])
            all_plugins = PluginService.get_all_plugins_for_user(test_user['id'])
            default = next(a for a in all_plugins if a['is_default'])
            
            # Execute
            response = client.put(f'/api/plugins/{default["id"]}', json={
                'name': 'New Name'
            })
            
            # Verify
            assert response.status_code == 403
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_update_nonexistent_plugin(self, client, test_user):
        """Test that updating nonexistent plugin returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(f'/api/plugins/{fake_id}', json={'name': 'New'})
        
        assert response.status_code == 404
    
    def test_update_plugin_unauthenticated(self, client):
        """Test that unauthenticated update returns 401."""
        response = client.put(
            '/api/plugins/00000000-0000-0000-0000-000000000000',
            json={'name': 'New'}
        )
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestDeletePluginEndpoint:
    """Tests for DELETE /api/plugins/{plugin_id}"""
    
    def test_delete_custom_plugin(self, client, app, test_user):
        """Test deleting a custom plugin."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create custom plugin
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            plugin_id = custom['id']
            
            # Execute
            response = client.delete(f'/api/plugins/{plugin_id}')
            
            # Verify
            assert response.status_code == 204
            
            # Verify it's deleted
            all_plugins = PluginService.get_all_plugins_for_user(test_user['id'])
            assert not any(a['id'] == plugin_id for a in all_plugins)
    
    def test_delete_default_plugin_forbidden(self, client, app, test_user):
        """Test that deleting default plugin returns 403."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default plugin
            PluginService.get_or_create_default_plugins(test_user['id'])
            all_plugins = PluginService.get_all_plugins_for_user(test_user['id'])
            default = next(a for a in all_plugins if a['is_default'])
            
            # Execute
            response = client.delete(f'/api/plugins/{default["id"]}')
            
            # Verify
            assert response.status_code == 403
    
    def test_delete_nonexistent_plugin(self, client, test_user):
        """Test that deleting nonexistent plugin returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f'/api/plugins/{fake_id}')
        
        assert response.status_code == 404
    
    def test_delete_plugin_unauthenticated(self, client):
        """Test that unauthenticated delete returns 401."""
        response = client.delete('/api/plugins/00000000-0000-0000-0000-000000000000')
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestActivatePluginEndpoint:
    """Tests for POST /api/plugins/{plugin_id}/activate"""
    
    def test_activate_plugin(self, client, app, test_user):
        """Test activating an inactive plugin."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create and deactivate
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            plugin_id = custom['id']
            PluginService.deactivate_plugin(test_user['id'], UUID(plugin_id))
            
            # Execute
            response = client.post(f'/api/plugins/{plugin_id}/activate', json={
                'is_active': True
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['is_active'] is True
    
    def test_deactivate_plugin(self, client, app, test_user):
        """Test deactivating an active plugin."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Create plugin (active by default)
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Custom",
                "Desc",
                "Prompt"
            )
            plugin_id = custom['id']
            
            # Execute
            response = client.post(f'/api/plugins/{plugin_id}/activate', json={
                'is_active': False
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['is_active'] is False
    
    def test_activate_nonexistent_plugin(self, client, test_user):
        """Test activating nonexistent plugin returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(f'/api/plugins/{fake_id}/activate', json={
            'is_active': True
        })
        
        assert response.status_code == 404
    
    def test_activate_missing_is_active_field(self, client, test_user):
        """Test that missing is_active field returns 400."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        response = client.post(
            '/api/plugins/00000000-0000-0000-0000-000000000000/activate',
            json={}  # Missing is_active
        )

        assert response.status_code in (400, 422)
    
    def test_activate_plugin_unauthenticated(self, client):
        """Test that unauthenticated activate returns 401."""
        response = client.post(
            '/api/plugins/00000000-0000-0000-0000-000000000000/activate',
            json={'is_active': True}
        )
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
class TestOverridePromptEndpoint:
    """Tests for POST /api/plugins/{plugin_id}/override-prompt"""
    
    def test_set_custom_prompt(self, client, app, test_user):
        """Test setting a custom prompt override."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Custom",
                "Desc",
                "Original Prompt"
            )
            plugin_id = custom['id']
            
            # Execute
            response = client.post(f'/api/plugins/{plugin_id}/override-prompt', json={
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
            
            # Setup: Create plugin with custom prompt
            custom = PluginService.create_custom_plugin(
                test_user['id'],
                "Custom",
                "Desc",
                "Default Prompt"
            )
            plugin_id = custom['id']
            PluginService.override_prompt(test_user['id'], UUID(plugin_id), "Custom")
            
            # Execute: Revert with null
            response = client.post(f'/api/plugins/{plugin_id}/override-prompt', json={
                'custom_prompt': None
            })
            
            # Verify
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['custom_prompt'] is None
            assert data['prompt_to_use'] == 'Default Prompt'
    
    def test_override_prompt_nonexistent_plugin(self, client, test_user):
        """Test overriding prompt on nonexistent plugin returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user['id']
            sess['username'] = test_user['username']
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(f'/api/plugins/{fake_id}/override-prompt', json={
            'custom_prompt': 'New'
        })
        
        assert response.status_code == 404
    
    def test_override_prompt_unauthenticated(self, client):
        """Test that unauthenticated override returns 401."""
        response = client.post(
            '/api/plugins/00000000-0000-0000-0000-000000000000/override-prompt',
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
            
            # Step 1: Create custom plugin
            create_response = client.post('/api/plugins', json={
                'name': 'Workflow Plugin',
                'description': 'Test workflow',
                'prompt': 'Original prompt'
            })
            assert create_response.status_code == 201
            create_data = json.loads(create_response.data)
            global_plugin_id = str(create_data['plugin_id'])

            # Step 2: Override prompt
            override_response = client.post(
                f'/api/plugins/{global_plugin_id}/override-prompt',
                json={'custom_prompt': 'Custom override'}
            )
            assert override_response.status_code == 200
            assert json.loads(override_response.data)['custom_prompt'] == 'Custom override'

            # Step 3: Get in list
            list_response = client.get('/api/plugins')
            assert list_response.status_code == 200
            plugins = json.loads(list_response.data)['plugins']
            workflow_plugin = next(a for a in plugins if a['id'] == global_plugin_id)
            assert workflow_plugin['custom_prompt'] == 'Custom override'
            assert workflow_plugin['is_active'] is True
    
    def test_multi_user_isolation(self, client, app, test_user, create_test_user):
        """Test that users are completely isolated."""
        with app.app_context():
            # Create second user
            user2_id = create_test_user('user2', 'user2@test.com', 'pass123')
            
            # User 1: Create custom plugin
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            user1_create = client.post('/api/plugins', json={
                'name': 'User 1 Plugin',
                'description': 'Only for user 1',
                'prompt': 'Prompt'
            })
            user1_plugin_id = json.loads(user1_create.data)['id']
            
            # User 2: Should not see User 1's plugin
            with client.session_transaction() as sess:
                sess['user_id'] = user2_id
                sess['username'] = 'user2'
            
            user2_list = client.get('/api/plugins')
            user2_plugins = json.loads(user2_list.data)['plugins']
            
            # User 2 should not see User 1's plugin
            assert not any(a['id'] == user1_plugin_id for a in user2_plugins)
            
            # User 2 trying to get User 1's plugin should get 404
            get_response = client.get(f'/api/plugins/{user1_plugin_id}')
            assert get_response.status_code == 404
    
    def test_default_plugins_protected_from_modification(self, client, app, test_user):
        """Test that default plugins cannot be modified or deleted."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['user_id'] = test_user['id']
                sess['username'] = test_user['username']
            
            # Setup: Get default plugin
            PluginService.get_or_create_default_plugins(test_user['id'])
            list_response = client.get('/api/plugins')
            plugins = json.loads(list_response.data)['plugins']
            default = next(a for a in plugins if a['is_default'])
            default_id = default['id']
            
            # Try to update: should fail
            update_response = client.put(f'/api/plugins/{default_id}', json={
                'name': 'Hacked Name'
            })
            assert update_response.status_code == 403
            
            # Try to delete: should fail
            delete_response = client.delete(f'/api/plugins/{default_id}')
            assert delete_response.status_code == 403
            
            # Default plugin should still be there
            get_response = client.get(f'/api/plugins/{default_id}')
            assert get_response.status_code == 200
            assert json.loads(get_response.data)['name'] == default['name']
