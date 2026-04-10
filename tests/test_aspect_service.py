"""Tests for PluginService."""

from uuid import UUID

import pytest

from models.database import User
from services.exceptions import (
    PluginDeletionError,
)
from services.plugin_service import DEFAULT_PLUGINS, PluginService


@pytest.mark.db
class TestPluginService:
    """Tests for PluginService."""

    def test_seed_defaults_on_first_user(self, app):
        """Test seeding default plugins for a new user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            PluginService.get_or_create_default_plugins(user.id)

            plugins = PluginService.get_all_plugins_for_user(user.id)

            # Should have 16 default plugins (RMM criteria)
            assert len(plugins) == len(DEFAULT_PLUGINS)
            assert all(a["is_default"] is True for a in plugins)

    def test_seed_defaults_idempotent(self, app):
        """Test that seeding defaults is idempotent."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed twice
            PluginService.get_or_create_default_plugins(user.id)
            PluginService.get_or_create_default_plugins(user.id)

            # Should still have same count (not doubled)
            plugins = PluginService.get_all_plugins_for_user(user.id)
            assert len(plugins) == len(DEFAULT_PLUGINS)

    def test_get_all_plugins_for_user(self, app):
        """Test getting all plugins for a user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            # Add custom plugin
            PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom Plugin",
                description="Custom Desc",
                prompt="Custom Prompt",
            )

            all_plugins = PluginService.get_all_plugins_for_user(user.id)

            # Should have default + 1 custom
            assert len(all_plugins) == len(DEFAULT_PLUGINS) + 1
            assert any(a["name"] == "Custom Plugin" for a in all_plugins)
            assert all(
                set(a.keys()) == {"id", "name", "description", "is_default", "is_active", "custom_prompt"}
                for a in all_plugins
            )

    def test_create_custom_plugin(self, app):
        """Test creating a custom plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            result = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )

            assert result["name"] == "Custom"
            assert result["description"] == "Desc"
            assert result["is_default"] is False
            assert result["is_active"] is True
            assert result["custom_prompt"] is None

    def test_update_custom_plugin(self, app):
        """Test updating a custom plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )

            plugin_id = UUID(custom["id"])

            result = PluginService.update_custom_plugin(
                user_id=user.id,
                plugin_id=plugin_id,
                name="Updated",
                description="Updated Desc",
                prompt="Updated Prompt",
            )

            assert result["name"] == "Updated"
            assert result["description"] == "Updated Desc"

    def test_update_default_plugin_fails(self, app):
        """Test that updating a default plugin raises error."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            default_plugin = next(a for a in all_plugins if a["is_default"])

            with pytest.raises(PluginDeletionError):
                PluginService.update_custom_plugin(
                    user_id=user.id,
                    plugin_id=UUID(default_plugin["id"]),
                    name="New Name",
                )

    def test_delete_custom_plugin(self, app):
        """Test deleting a custom plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )

            plugin_id = UUID(custom["id"])

            PluginService.delete_custom_plugin(user_id=user.id, plugin_id=plugin_id)

            # Should be gone from user's plugins
            remaining = PluginService.get_all_plugins_for_user(user.id)
            assert not any(a["id"] == str(plugin_id) for a in remaining)

    def test_delete_default_plugin_fails(self, app):
        """Test that deleting a default plugin raises error."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            default_plugin = next(a for a in all_plugins if a["is_default"])

            with pytest.raises(PluginDeletionError):
                PluginService.delete_custom_plugin(
                    user_id=user.id,
                    plugin_id=UUID(default_plugin["id"]),
                )

    def test_activate_plugin(self, app):
        """Test activating an plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )

            plugin_id = UUID(custom["id"])

            # Deactivate
            PluginService.deactivate_plugin(user_id=user.id, plugin_id=plugin_id)

            # Activate
            PluginService.activate_plugin(user_id=user.id, plugin_id=plugin_id)

            plugins = PluginService.get_all_plugins_for_user(user.id)
            plugin = next(a for a in plugins if a["id"] == str(plugin_id))
            assert plugin["is_active"] is True

    def test_deactivate_plugin(self, app):
        """Test deactivating an plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )

            plugin_id = UUID(custom["id"])

            PluginService.deactivate_plugin(user_id=user.id, plugin_id=plugin_id)

            plugins = PluginService.get_all_plugins_for_user(user.id)
            plugin = next(a for a in plugins if a["id"] == str(plugin_id))
            assert plugin["is_active"] is False

    def test_override_prompt(self, app):
        """Test overriding a prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Original Prompt",
            )

            plugin_id = UUID(custom["id"])

            PluginService.override_prompt(
                user_id=user.id,
                plugin_id=plugin_id,
                custom_prompt="Custom Prompt",
            )

            plugins = PluginService.get_all_plugins_for_user(user.id)
            plugin = next(a for a in plugins if a["id"] == str(plugin_id))
            assert plugin["custom_prompt"] == "Custom Prompt"

    def test_get_active_plugins_for_evaluation(self, app):
        """Test getting active plugins for evaluation."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            active = PluginService.get_active_plugins_for_evaluation(user.id)

            # Should have all default plugins active
            assert len(active) == len(DEFAULT_PLUGINS)
            assert all(set(a.keys()) == {"id", "name", "description", "prompt_to_use"} for a in active)

    def test_get_active_plugins_uses_custom_prompt(self, app):
        """Test that custom prompt is used in evaluation."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Original Prompt",
            )

            plugin_id = UUID(custom["id"])

            # Override prompt
            PluginService.override_prompt(
                user_id=user.id,
                plugin_id=plugin_id,
                custom_prompt="Custom Prompt",
            )

            active = PluginService.get_active_plugins_for_evaluation(user.id)
            custom_plugin = next(a for a in active if a["id"] == str(plugin_id))

            # Should use custom prompt
            assert custom_plugin["prompt_to_use"] == "Custom Prompt"

    def test_get_active_plugins_uses_default_prompt(self, app):
        """Test that default prompt is used when no custom prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Default Prompt",
            )

            plugin_id = UUID(custom["id"])

            active = PluginService.get_active_plugins_for_evaluation(user.id)
            custom_plugin = next(a for a in active if a["id"] == str(plugin_id))

            # Should use default prompt
            assert custom_plugin["prompt_to_use"] == "Default Prompt"

    def test_get_active_plugins_excludes_inactive(self, app):
        """Test that inactive plugins are excluded."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            first_plugin = all_plugins[0]

            # Deactivate first plugin
            PluginService.deactivate_plugin(
                user_id=user.id,
                plugin_id=UUID(first_plugin["id"]),
            )

            active = PluginService.get_active_plugins_for_evaluation(user.id)

            # Should have one fewer (one deactivated)
            assert len(active) == len(DEFAULT_PLUGINS) - 1
            assert not any(a["id"] == first_plugin["id"] for a in active)


@pytest.mark.db
class TestPluginServiceIntegration:
    """Integration tests for PluginService."""

    def test_full_workflow(self, app):
        """Test full workflow: new user -> seed -> custom -> override -> evaluate."""
        with app.app_context():
            # 1. Create user
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # 2. Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            assert len(all_plugins) == len(DEFAULT_PLUGINS)

            # 3. Create custom plugin
            custom = PluginService.create_custom_plugin(
                user_id=user.id,
                name="Custom Plugin",
                description="Custom Desc",
                prompt="Custom Prompt",
            )

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            assert len(all_plugins) == len(DEFAULT_PLUGINS) + 1

            # 4. Override prompt
            plugin_id = UUID(custom["id"])
            PluginService.override_prompt(
                user_id=user.id,
                plugin_id=plugin_id,
                custom_prompt="Overridden Prompt",
            )

            # 5. Get for evaluation
            active = PluginService.get_active_plugins_for_evaluation(user.id)
            custom_eval = next(a for a in active if a["id"] == str(plugin_id))
            assert custom_eval["prompt_to_use"] == "Overridden Prompt"

    def test_multiple_users_isolated(self, app):
        """Test that multiple users have isolated plugins."""
        with app.app_context():
            # Create two users
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

            # Seed defaults for both
            PluginService.get_or_create_default_plugins(user1.id)
            PluginService.get_or_create_default_plugins(user2.id)

            # User1 creates custom plugin
            custom1 = PluginService.create_custom_plugin(
                user_id=user1.id,
                name="User1 Custom",
                description="Desc",
                prompt="Prompt",
            )

            # Check isolation
            user1_plugins = PluginService.get_all_plugins_for_user(user1.id)
            user2_plugins = PluginService.get_all_plugins_for_user(user2.id)

            assert len(user1_plugins) == len(DEFAULT_PLUGINS) + 1  # default + 1 custom
            assert len(user2_plugins) == len(DEFAULT_PLUGINS)  # default only

            # User1's custom should not be in user2's list
            user2_ids = {UUID(a["id"]) for a in user2_plugins}
            assert UUID(custom1["id"]) not in user2_ids

    def test_default_plugins_cannot_be_modified_via_service(self, app):
        """Test that default plugins cannot be modified through service."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            # Seed defaults
            PluginService.get_or_create_default_plugins(user.id)

            all_plugins = PluginService.get_all_plugins_for_user(user.id)
            default = next(a for a in all_plugins if a["is_default"])
            default_id = UUID(default["id"])

            # Try to update - should fail
            with pytest.raises(PluginDeletionError):
                PluginService.update_custom_plugin(
                    user_id=user.id,
                    plugin_id=default_id,
                    name="Modified",
                )

            # Try to delete - should fail
            with pytest.raises(PluginDeletionError):
                PluginService.delete_custom_plugin(
                    user_id=user.id,
                    plugin_id=default_id,
                )

    def test_prompt_override_independent_per_user(self, app):
        """Test that prompt overrides are independent per user."""
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

            # Seed defaults for both
            PluginService.get_or_create_default_plugins(user1.id)
            PluginService.get_or_create_default_plugins(user2.id)

            # Get first default plugin
            user1_plugins = PluginService.get_all_plugins_for_user(user1.id)
            plugin_id = UUID(user1_plugins[0]["id"])

            # Override for user1
            PluginService.override_prompt(
                user_id=user1.id,
                plugin_id=plugin_id,
                custom_prompt="User1 Override",
            )

            # User1 should have override
            user1_eval = PluginService.get_active_plugins_for_evaluation(user1.id)
            user1_plugin = next(a for a in user1_eval if a["id"] == str(plugin_id))
            assert user1_plugin["prompt_to_use"] == "User1 Override"

            # User2 should use default
            user2_eval = PluginService.get_active_plugins_for_evaluation(user2.id)
            user2_plugin = next(a for a in user2_eval if a["id"] == str(plugin_id))
            assert user2_plugin["prompt_to_use"] != "User1 Override"
