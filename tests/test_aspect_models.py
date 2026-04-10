"""Tests for Plugin and UserPlugin models."""

from datetime import datetime

import pytest

from models.database import User
from models.plugin import Plugin, UserPlugin


@pytest.mark.db
class TestPluginModel:
    """Tests for Plugin model."""

    def test_plugin_creation_with_all_fields(self, app):
        """Test creating an plugin with all fields."""
        with app.app_context():
            plugin = Plugin.create(
                name="Test Plugin",
                description="Test Description",
                prompt="Test Prompt",
                is_default=True,
            )

            assert plugin.id is not None
            assert plugin.name == "Test Plugin"
            assert plugin.description == "Test Description"
            assert plugin.prompt == "Test Prompt"
            assert plugin.is_default is True
            assert isinstance(plugin.created_at, datetime)
            assert isinstance(plugin.updated_at, datetime)

    def test_plugin_creation_default_is_false(self, app):
        """Test that is_default defaults to False."""
        with app.app_context():
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            assert plugin.is_default is False

    def test_plugin_timestamps_auto_set(self, app):
        """Test that timestamps are automatically set."""
        with app.app_context():
            before = datetime.now()
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            after = datetime.now()

            assert before <= plugin.created_at <= after
            assert before <= plugin.updated_at <= after

    def test_plugin_multiple_creation(self, app):
        """Test creating multiple plugins."""
        with app.app_context():
            plugin1 = Plugin.create(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = Plugin.create(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )

            assert plugin1.id != plugin2.id
            assert plugin1.name != plugin2.name


@pytest.mark.db
class TestUserPluginModel:
    """Tests for UserPlugin model."""

    def test_user_plugin_creation(self, app):
        """Test creating a user plugin."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            user_plugin = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin.id,
                is_active=True,
            )

            assert user_plugin.id is not None
            assert user_plugin.user_id_id == user.id
            assert user_plugin.plugin_id_id == plugin.id
            assert user_plugin.is_active is True
            assert user_plugin.custom_prompt is None
            assert user_plugin.deleted_at is None
            assert isinstance(user_plugin.created_at, datetime)
            assert isinstance(user_plugin.updated_at, datetime)

    def test_user_plugin_custom_prompt_nullable(self, app):
        """Test that custom_prompt is nullable."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            user_plugin = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin.id,
                custom_prompt=None,
            )

            assert user_plugin.custom_prompt is None

            # Update with a custom prompt
            user_plugin.custom_prompt = "Custom Prompt"
            user_plugin.save()

            # Refresh from DB
            user_plugin = UserPlugin.get_by_id(user_plugin.id)
            assert user_plugin.custom_prompt == "Custom Prompt"

    def test_user_plugin_unique_constraint(self, app):
        """Test that unique(user_id, plugin_id) constraint is enforced."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            # Create first user plugin
            UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin.id,
            )

            # Try to create duplicate - should raise IntegrityError
            with pytest.raises(Exception):  # Peewee raises IntegrityError
                UserPlugin.create(
                    user_id=user.id,
                    plugin_id=plugin.id,
                )

    def test_user_plugin_multiple_per_user(self, app):
        """Test that a user can have multiple plugins."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )

            plugin1 = Plugin.create(
                name="Plugin 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            plugin2 = Plugin.create(
                name="Plugin 2",
                description="Desc 2",
                prompt="Prompt 2",
            )

            ua1 = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin1.id,
            )
            ua2 = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin2.id,
            )

            assert ua1.id != ua2.id
            assert ua1.plugin_id != ua2.plugin_id

    def test_user_plugin_is_active_default(self, app):
        """Test that is_active defaults to True."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            user_plugin = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin.id,
            )

            assert user_plugin.is_active is True

    def test_user_plugin_soft_delete(self, app):
        """Test that deleted_at marks soft delete."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            plugin = Plugin.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )

            user_plugin = UserPlugin.create(
                user_id=user.id,
                plugin_id=plugin.id,
            )

            # Initially should be None
            assert user_plugin.deleted_at is None

            # Mark as deleted
            user_plugin.deleted_at = datetime.now()
            user_plugin.save()

            # Refresh from DB
            user_plugin = UserPlugin.get_by_id(user_plugin.id)
            assert user_plugin.deleted_at is not None
