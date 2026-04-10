"""Repository layer for Plugin and UserPlugin models."""

from typing import List, Optional, Union
from uuid import UUID

from models.plugin import Plugin, UserPlugin

_UNSET = object()  # Sentinel to distinguish "not provided" from None


class PluginRepository:
    """Data access layer for Plugin model."""

    @staticmethod
    def get_plugin(plugin_id: UUID) -> Optional[Plugin]:
        """Get plugin by ID."""
        try:
            return Plugin.get_by_id(plugin_id)
        except Plugin.DoesNotExist:
            return None

    @staticmethod
    def get_all_plugins() -> List[Plugin]:
        """Get all plugins."""
        try:
            return list(Plugin.select().order_by(Plugin.created_at))
        except Exception:
            return []

    @staticmethod
    def get_default_plugins() -> List[Plugin]:
        """Get all default plugins."""
        try:
            return list(Plugin.select().where(Plugin.is_default).order_by(Plugin.created_at))
        except Exception:
            return []

    @staticmethod
    def create_plugin(name: str, description: str, prompt: str, is_default: bool = False) -> Plugin:
        """Create a new plugin."""
        return Plugin.create(name=name, description=description, prompt=prompt, is_default=is_default)

    @staticmethod
    def update_plugin(
        plugin_id: UUID, name: Optional[str] = None, description: Optional[str] = None, prompt: Optional[str] = None
    ) -> Optional[Plugin]:
        """Update plugin (name, description, prompt only)."""
        plugin = PluginRepository.get_plugin(plugin_id)
        if not plugin:
            return None

        if name is not None:
            plugin.name = name
        if description is not None:
            plugin.description = description
        if prompt is not None:
            plugin.prompt = prompt

        plugin.save()
        return plugin

    @staticmethod
    def delete_plugin(plugin_id: UUID) -> bool:
        """Delete plugin (only if NOT is_default)."""
        from services.exceptions import PluginDeletionError

        plugin = PluginRepository.get_plugin(plugin_id)
        if not plugin:
            return False

        if plugin.is_default:
            raise PluginDeletionError("Cannot delete default plugin")

        plugin.delete_instance()
        return True


class UserPluginRepository:
    """Data access layer for UserPlugin model."""

    @staticmethod
    def get_user_plugins(user_id: Union[int, UUID]) -> List[UserPlugin]:
        """Get all plugins for a user (including deleted)."""
        try:
            return list(UserPlugin.select().where(UserPlugin.user_id == user_id).order_by(UserPlugin.created_at))
        except Exception:
            return []

    @staticmethod
    def get_active_plugins(user_id: Union[int, UUID]) -> List[Plugin]:
        """Get only active plugins for a user (JOIN with Plugin)."""
        try:
            return list(
                Plugin.select()
                .join(UserPlugin)
                .where((UserPlugin.user_id == user_id) & (UserPlugin.is_active) & (UserPlugin.deleted_at.is_null()))
                .order_by(Plugin.created_at)
            )
        except Exception:
            return []

    @staticmethod
    def get_user_plugin(user_id: Union[int, UUID], plugin_id: Union[str, UUID]) -> Optional[UserPlugin]:
        """Get specific user plugin."""
        try:
            return UserPlugin.get((UserPlugin.user_id == user_id) & (UserPlugin.plugin_id == plugin_id))
        except UserPlugin.DoesNotExist:
            return None

    @staticmethod
    def create_user_plugin(
        user_id: Union[int, UUID], plugin_id: Union[str, UUID], custom_prompt: Optional[str] = None
    ) -> UserPlugin:
        """Create user plugin entry."""
        return UserPlugin.create(user_id=user_id, plugin_id=plugin_id, custom_prompt=custom_prompt, is_active=True)

    @staticmethod
    def update_user_plugin(
        user_id: Union[int, UUID], plugin_id: Union[str, UUID], is_active: Optional[bool] = None, custom_prompt=_UNSET
    ) -> Optional[UserPlugin]:
        """Update user plugin (is_active and/or custom_prompt)."""
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            return None

        if is_active is not None:
            user_plugin.is_active = is_active
        if custom_prompt is not _UNSET:
            user_plugin.custom_prompt = custom_prompt

        user_plugin.save()
        return user_plugin

    @staticmethod
    def delete_user_plugin(user_id: Union[int, UUID], plugin_id: Union[str, UUID]) -> bool:
        """Soft delete user plugin (mark deleted_at)."""
        from datetime import datetime

        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            return False

        user_plugin.deleted_at = datetime.now()
        user_plugin.save()
        return True
