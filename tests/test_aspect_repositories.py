"""Tests for PluginRepository and UserPluginRepository."""

import pytest
from uuid import UUID
from models.database import User
from models.plugin import Plugin, UserPlugin
from repositories.plugin_repository import PluginRepository, UserPluginRepository
from services.exceptions import PluginDeletionError


@pytest.mark.db
class TestPluginRepository:
    """Tests for PluginRepository."""
    
    def test_create_plugin(self, app):
        """Test creating an plugin."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Test Plugin",
                description="Test Description",
                prompt="Test Prompt",
                is_default=False,
            )
            
            assert plugin.id is not None
            assert plugin.name == "Test Plugin"
            assert plugin.is_default is False
    
    def test_create_default_plugin(self, app):
        """Test creating a default plugin."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Default Plugin",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            
            assert plugin.is_default is True
    
    def test_get_plugin_by_id(self, app):
        """Test getting an plugin by ID."""
        with app.app_context():
            created = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            retrieved = PluginRepository.get_plugin(created.id)
            
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.name == "Test"
    
    def test_get_plugin_by_id_not_found(self, app):
        """Test getting a non-existent plugin returns None."""
        with app.app_context():
            from uuid import uuid4
            result = PluginRepository.get_plugin(uuid4())
            assert result is None
    
    def test_get_all_plugins(self, app):
        """Test getting all plugins."""
        with app.app_context():
            plugin1 = PluginRepository.create_plugin(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = PluginRepository.create_plugin(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            all_plugins = PluginRepository.get_all_plugins()
            
            assert len(all_plugins) >= 2
            assert any(a.id == plugin1.id for a in all_plugins)
            assert any(a.id == plugin2.id for a in all_plugins)
    
    def test_get_default_plugins(self, app):
        """Test getting only default plugins."""
        with app.app_context():
            default = PluginRepository.create_plugin(
                name="Default",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            non_default = PluginRepository.create_plugin(
                name="Non-Default",
                description="Desc",
                prompt="Prompt",
                is_default=False,
            )
            
            defaults = PluginRepository.get_default_plugins()
            
            assert any(a.id == default.id for a in defaults)
            assert not any(a.id == non_default.id for a in defaults)
    
    def test_update_plugin(self, app):
        """Test updating an plugin."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Original",
                description="Original Desc",
                prompt="Original Prompt",
            )
            
            updated = PluginRepository.update_plugin(
                plugin.id,
                name="Updated",
                description="Updated Desc",
                prompt="Updated Prompt",
            )
            
            assert updated.name == "Updated"
            assert updated.description == "Updated Desc"
            assert updated.prompt == "Updated Prompt"
    
    def test_update_plugin_partial(self, app):
        """Test updating only some fields."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Original",
                description="Original Desc",
                prompt="Original Prompt",
            )
            
            updated = PluginRepository.update_plugin(
                plugin.id,
                name="Updated",
            )
            
            assert updated.name == "Updated"
            assert updated.description == "Original Desc"
            assert updated.prompt == "Original Prompt"
    
    def test_update_plugin_not_found(self, app):
        """Test updating a non-existent plugin."""
        with app.app_context():
            from uuid import uuid4
            result = PluginRepository.update_plugin(uuid4(), name="New")
            assert result is None
    
    def test_delete_non_default_plugin(self, app):
        """Test deleting a non-default plugin succeeds."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Non-Default",
                description="Desc",
                prompt="Prompt",
                is_default=False,
            )
            
            result = PluginRepository.delete_plugin(plugin.id)
            
            assert result is True
            assert PluginRepository.get_plugin(plugin.id) is None
    
    def test_delete_default_plugin_fails(self, app):
        """Test deleting a default plugin raises PluginDeletionError."""
        with app.app_context():
            plugin = PluginRepository.create_plugin(
                name="Default",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            
            with pytest.raises(PluginDeletionError):
                PluginRepository.delete_plugin(plugin.id)
    
    def test_delete_non_existent_plugin(self, app):
        """Test deleting a non-existent plugin returns False."""
        with app.app_context():
            from uuid import uuid4
            result = PluginRepository.delete_plugin(uuid4())
            assert result is False
    
    def test_update_multiple_plugins_isolation(self, app):
        """Test that updating multiple plugins doesn't affect others."""
        with app.app_context():
            plugin1 = PluginRepository.create_plugin(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = PluginRepository.create_plugin(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            PluginRepository.update_plugin(plugin1.id, name="Updated 1")
            
            updated1 = PluginRepository.get_plugin(plugin1.id)
            unchanged2 = PluginRepository.get_plugin(plugin2.id)
            
            assert updated1.name == "Updated 1"
            assert unchanged2.name == "Plugin 2"


@pytest.mark.db
class TestUserPluginRepository:
    """Tests for UserPluginRepository."""
    
    def test_create_user_plugin(self, app):
        """Test creating a user plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_plugin = UserPluginRepository.create_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
            )
            
            assert user_plugin.user_id == user.id
            assert user_plugin.plugin_id == plugin.id
            assert user_plugin.is_active is True
    
    def test_create_user_plugin_with_custom_prompt(self, app):
        """Test creating a user plugin with custom prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_plugin = UserPluginRepository.create_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
                custom_prompt="Custom Prompt",
            )
            
            assert user_plugin.custom_prompt == "Custom Prompt"
    
    def test_get_user_plugin(self, app):
        """Test getting a specific user plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            created = UserPluginRepository.create_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
            )
            
            retrieved = UserPluginRepository.get_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
            )
            
            assert retrieved is not None
            assert retrieved.id == created.id
    
    def test_get_user_plugin_not_found(self, app):
        """Test getting a non-existent user plugin."""
        with app.app_context():
            from uuid import uuid4
            result = UserPluginRepository.get_user_plugin(uuid4(), uuid4())
            assert result is None
    
    def test_get_user_plugins(self, app):
        """Test getting all plugins for a user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            plugin1 = PluginRepository.create_plugin(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = PluginRepository.create_plugin(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin1.id)
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin2.id)
            
            user_plugins = UserPluginRepository.get_user_plugins(user.id)
            
            assert len(user_plugins) == 2
            assert any(ua.plugin_id == plugin1.id for ua in user_plugins)
            assert any(ua.plugin_id == plugin2.id for ua in user_plugins)
    
    def test_get_active_plugins(self, app):
        """Test getting only active plugins."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            plugin1 = PluginRepository.create_plugin(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = PluginRepository.create_plugin(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            ua1 = UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin1.id)
            ua2 = UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin2.id)
            
            # Deactivate plugin2
            UserPluginRepository.update_user_plugin(user.id, plugin2.id, is_active=False)
            
            active = UserPluginRepository.get_active_plugins(user.id)
            
            assert len(active) == 1
            assert active[0].id == plugin1.id
    
    def test_get_active_plugins_excludes_soft_deleted(self, app):
        """Test that soft-deleted plugins are excluded from active."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin.id)
            
            # Soft delete
            UserPluginRepository.delete_user_plugin(user.id, plugin.id)
            
            active = UserPluginRepository.get_active_plugins(user.id)
            
            assert len(active) == 0
    
    def test_update_user_plugin_is_active(self, app):
        """Test updating is_active flag."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin.id)
            
            updated = UserPluginRepository.update_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
                is_active=False,
            )
            
            assert updated.is_active is False
    
    def test_update_user_plugin_custom_prompt(self, app):
        """Test updating custom_prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin.id)
            
            updated = UserPluginRepository.update_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
                custom_prompt="Custom",
            )
            
            assert updated.custom_prompt == "Custom"
    
    def test_update_user_plugin_both_fields(self, app):
        """Test updating both is_active and custom_prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin.id)
            
            updated = UserPluginRepository.update_user_plugin(
                user_id=user.id,
                plugin_id=plugin.id,
                is_active=False,
                custom_prompt="Custom",
            )
            
            assert updated.is_active is False
            assert updated.custom_prompt == "Custom"
    
    def test_delete_user_plugin(self, app):
        """Test soft deleting a user plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserPluginRepository.create_user_plugin(user_id=user.id, plugin_id=plugin.id)
            
            result = UserPluginRepository.delete_user_plugin(user.id, plugin.id)
            
            assert result is True
            
            # Check that deleted_at is set
            user_plugin = UserPluginRepository.get_user_plugin(user.id, plugin.id)
            assert user_plugin.deleted_at is not None
    
    def test_delete_user_plugin_not_found(self, app):
        """Test deleting a non-existent user plugin."""
        with app.app_context():
            from uuid import uuid4
            result = UserPluginRepository.delete_user_plugin(uuid4(), uuid4())
            assert result is False
    
    def test_multiple_users_isolated(self, app):
        """Test that multiple users have isolated plugin states."""
        with app.app_context():
            user1 = User.create(
                username="user1",
                email="user1@example.com",
                password_hash="hash",
            )
            user2 = User.create(
                username="user2",
                email="user2@example.com",
                password_hash="hash",
            )
            
            plugin = PluginRepository.create_plugin(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            ua1 = UserPluginRepository.create_user_plugin(user_id=user1.id, plugin_id=plugin.id)
            ua2 = UserPluginRepository.create_user_plugin(user_id=user2.id, plugin_id=plugin.id)
            
            # Update user1's plugin
            UserPluginRepository.update_user_plugin(
                user_id=user1.id,
                plugin_id=plugin.id,
                is_active=False,
            )
            
            # Check user2 is unaffected
            user2_plugin = UserPluginRepository.get_user_plugin(user2.id, plugin.id)
            assert user2_plugin.is_active is True
