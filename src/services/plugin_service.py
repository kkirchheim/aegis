"""Plugin service layer - business logic for plugin management."""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from repositories.plugin_repository import PluginRepository, UserPluginRepository
from services.exceptions import (
    PluginDeletionError,
    PluginNotFoundError,
    UserPluginNotFoundError,
)

# Default plugins to seed for new users — based on the Reproducibility Maturity Model (RMM)
DEFAULT_PLUGINS = [
    # RMM Level 0: Barriers to reproduction
    {
        "name": "RMM-0-1",
        "description": "Are any artifacts inaccessible or missing?",
        "prompt": "Are any artifacts inaccessible or missing?",
        "is_default": True,
    },
    {
        "name": "RMM-0-2",
        "description": "Are the environmental details insufficient to recreate the setup?",
        "prompt": "Are the environmental details insufficient to recreate the setup?",
        "is_default": True,
    },
    {
        "name": "RMM-0-3",
        "description": "Are versions unspecified or floating?",
        "prompt": "Are versions unspecified or floating?",
        "is_default": True,
    },
    {
        "name": "RMM-0-4",
        "description": "Does legal ambiguity prevent reuse?",
        "prompt": "Does legal ambiguity prevent reuse?",
        "is_default": True,
    },
    # RMM Level 1: Partial reproducibility
    {
        "name": "RMM-1-1",
        "description": "Are installation steps documented but potentially brittle?",
        "prompt": "Are installation steps documented but potentially brittle?",
        "is_default": True,
    },
    {
        "name": "RMM-1-2",
        "description": "Are versions given but not pinned at all hierarchy levels?",
        "prompt": "Are versions given but not pinned at all hierarchy levels?",
        "is_default": True,
    },
    {
        "name": "RMM-1-3",
        "description": "Are pipelines runnable but not fully automated?",
        "prompt": "Are pipelines runnable but not fully automated?",
        "is_default": True,
    },
    {
        "name": "RMM-1-4",
        "description": "Are licenses present but incomplete or unclear?",
        "prompt": "Are licenses present but incomplete or unclear?",
        "is_default": True,
    },
    # RMM Level 2: Reproducibility infrastructure
    {
        "name": "RMM-2-1",
        "description": "Is a containerized or automated pipeline provided?",
        "prompt": "Is a containerized or automated pipeline provided?",
        "is_default": True,
    },
    {
        "name": "RMM-2-2",
        "description": "Are all dependencies pinned, including OS, libraries, and models?",
        "prompt": "Are all dependencies pinned, including OS, libraries, and models?",
        "is_default": True,
    },
    {
        "name": "RMM-2-3",
        "description": "Are datasets and models persistently hosted with stable identifiers?",
        "prompt": "Are datasets and models persistently hosted with stable identifiers?",
        "is_default": True,
    },
    {
        "name": "RMM-2-4",
        "description": "Are all components licensed for reuse?",
        "prompt": "Are all components licensed for reuse?",
        "is_default": True,
    },
    # RMM Level 3: Full independent reproduction
    {
        "name": "RMM-3-1",
        "description": "Can the results be reproduced exactly using only the provided artifacts and instructions?",
        "prompt": "Can the results be reproduced exactly using only the provided artifacts and instructions?",
        "is_default": True,
    },
    {
        "name": "RMM-3-2",
        "description": "Was the reproduction performed independently, without author intervention?",
        "prompt": "Was the reproduction performed independently, without author intervention?",
        "is_default": True,
    },
    {
        "name": "RMM-3-3",
        "description": "Are all outputs (tables, figures, metrics) consistent with those reported in the paper?",
        "prompt": "Are all outputs (tables, figures, metrics) consistent with those reported in the paper?",
        "is_default": True,
    },
    {
        "name": "RMM-3-4",
        "description": "Does the reproduction process complete successfully in a clean environment?",
        "prompt": "Does the reproduction process complete successfully in a clean environment?",
        "is_default": True,
    },
]


class PluginService:
    """Business logic for plugin management."""

    @staticmethod
    def get_or_create_default_plugins(user_id: Union[int, UUID]) -> None:
        """Seed default plugins for a user on first login (idempotent)."""
        for plugin_data in DEFAULT_PLUGINS:
            # Get or create the global default plugin
            default_plugins = PluginRepository.get_default_plugins()
            plugin_exists = any(a.name == plugin_data["name"] for a in default_plugins)

            if plugin_exists:
                plugin = next(a for a in default_plugins if a.name == plugin_data["name"])
            else:
                plugin = PluginRepository.create_plugin(**plugin_data)

            # Create user plugin if it doesn't exist
            existing = UserPluginRepository.get_user_plugin(user_id, plugin.id)
            if not existing:
                UserPluginRepository.create_user_plugin(user_id, plugin.id, custom_prompt=None)

    @staticmethod
    def get_all_plugins_for_user(user_id: Union[int, UUID]) -> List[Dict[str, Any]]:
        """Get all plugins for user with their settings.

        Returns list of dicts with: {id, name, description, is_default, is_active, custom_prompt}
        """
        import sys

        # Ensure default plugins are seeded for this user
        try:
            PluginService.get_or_create_default_plugins(user_id)
        except Exception as e:
            print(f"ERROR seeding default plugins: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()

        user_plugins = UserPluginRepository.get_user_plugins(user_id)
        results = []

        for user_plugin in user_plugins:
            if user_plugin.deleted_at:
                continue  # Skip soft-deleted plugins

            plugin = user_plugin.plugin_id  # Peewee FK auto-resolves
            results.append(
                {
                    "id": str(plugin.id),
                    "name": plugin.name,
                    "description": plugin.description,
                    "is_default": plugin.is_default,
                    "is_active": user_plugin.is_active,
                    "custom_prompt": user_plugin.custom_prompt,
                }
            )

        return sorted(results, key=lambda x: x["name"])

    @staticmethod
    def create_custom_plugin(
        user_id: Union[int, UUID],
        name: str,
        description: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Create a custom plugin for a user.

        Creates both the global Plugin and UserPlugin entry.
        """
        # Create global plugin (not default)
        plugin = PluginRepository.create_plugin(
            name=name,
            description=description,
            prompt=prompt,
            is_default=False,
        )

        # Create user plugin entry
        UserPluginRepository.create_user_plugin(
            user_id=user_id,
            plugin_id=plugin.id,
            custom_prompt=None,
        )

        return {
            "id": str(plugin.id),
            "name": plugin.name,
            "description": plugin.description,
            "is_default": plugin.is_default,
            "is_active": True,
            "custom_prompt": None,
        }

    @staticmethod
    def update_custom_plugin(
        user_id: Union[int, UUID],
        plugin_id: Union[str, UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a custom plugin.

        Only non-default plugins can be updated.
        """
        plugin = PluginRepository.get_plugin(plugin_id)
        if not plugin:
            raise PluginNotFoundError(f"Plugin {plugin_id} not found")

        if plugin.is_default:
            raise PluginDeletionError("Cannot update default plugins")

        # Verify user has this plugin
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            raise UserPluginNotFoundError(f"User does not have plugin {plugin_id}")

        # Update global plugin
        updated_plugin = PluginRepository.update_plugin(
            plugin_id,
            name=name,
            description=description,
            prompt=prompt,
        )

        return {
            "id": str(updated_plugin.id),
            "name": updated_plugin.name,
            "description": updated_plugin.description,
            "is_default": updated_plugin.is_default,
            "is_active": user_plugin.is_active,
            "custom_prompt": user_plugin.custom_prompt,
        }

    @staticmethod
    def delete_custom_plugin(user_id: Union[int, UUID], plugin_id: Union[str, UUID]) -> None:
        """Delete a custom plugin.

        Only non-default plugins can be deleted.
        """
        plugin = PluginRepository.get_plugin(plugin_id)
        if not plugin:
            raise PluginNotFoundError(f"Plugin {plugin_id} not found")

        if plugin.is_default:
            raise PluginDeletionError("Cannot delete default plugins")

        # Verify user has this plugin
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            raise UserPluginNotFoundError(f"User does not have plugin {plugin_id}")

        # Soft delete user plugin
        UserPluginRepository.delete_user_plugin(user_id, plugin_id)

    @staticmethod
    def activate_plugin(user_id: Union[int, UUID], plugin_id: Union[str, UUID]) -> None:
        """Activate a plugin for a user."""
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            raise UserPluginNotFoundError(f"User does not have plugin {plugin_id}")

        UserPluginRepository.update_user_plugin(user_id, plugin_id, is_active=True)

    @staticmethod
    def deactivate_plugin(user_id: Union[int, UUID], plugin_id: Union[str, UUID]) -> None:
        """Deactivate a plugin for a user."""
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            raise UserPluginNotFoundError(f"User does not have plugin {plugin_id}")

        UserPluginRepository.update_user_plugin(user_id, plugin_id, is_active=False)

    @staticmethod
    def override_prompt(
        user_id: Union[int, UUID],
        plugin_id: Union[str, UUID],
        custom_prompt: str,
    ) -> None:
        """Override the prompt for a user's plugin."""
        user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
        if not user_plugin:
            raise UserPluginNotFoundError(f"User does not have plugin {plugin_id}")

        UserPluginRepository.update_user_plugin(user_id, plugin_id, custom_prompt=custom_prompt)

    @staticmethod
    def get_active_plugins_for_evaluation(
        user_id: Union[int, UUID],
    ) -> List[Dict[str, str]]:
        """Get active plugins ready for evaluation.

        Returns list of dicts with: {id, name, description, prompt_to_use}
        where prompt_to_use is custom_prompt if set, else default prompt.
        """
        # Ensure defaults are seeded before querying
        PluginService.get_or_create_default_plugins(user_id)
        active_plugins = UserPluginRepository.get_active_plugins(user_id)
        results = []

        for plugin in active_plugins:
            # Get the user's plugin settings
            user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin.id)

            # Use custom prompt if set, otherwise use default
            prompt_to_use = user_plugin.custom_prompt if user_plugin.custom_prompt else plugin.prompt

            results.append(
                {
                    "id": str(plugin.id),
                    "name": plugin.name,
                    "description": plugin.description,
                    "prompt_to_use": prompt_to_use,
                }
            )

        return sorted(results, key=lambda x: x["name"])
