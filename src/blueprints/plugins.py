"""API blueprint for plugin management endpoints.

This module provides REST API endpoints for managing reproducibility plugins,
including CRUD operations, activation/deactivation, and prompt overrides.
"""

from uuid import UUID
from flask import Blueprint, request, jsonify
from flask_apispec import doc, use_kwargs, marshal_with

from utils.decorators import require_auth_cookie_or_api_key, get_current_user_id
from schemas.plugin import (
    PluginCreateSchema, PluginUpdateSchema, ActivatePluginSchema,
    OverridePromptSchema, UserPluginSchema, PluginListSchema, PluginSchema
)
from schemas.common import ErrorSchema
from services.plugin_service import PluginService
from services.exceptions import (
    PluginNotFoundError, PluginDeletionError, UserPluginNotFoundError
)

plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')


def _build_user_plugin_response(plugin_id, user_id):
    """Helper to build a UserPluginSchema response.
    
    Args:
        plugin_id: UUID of the plugin
        user_id: UUID of the user
        
    Returns:
        Dict matching UserPluginSchema or None if not found
    """
    from repositories.plugin_repository import PluginRepository, UserPluginRepository
    
    plugin = PluginRepository.get_plugin(plugin_id)
    if not plugin:
        return None
    
    user_plugin = UserPluginRepository.get_user_plugin(user_id, plugin_id)
    if not user_plugin:
        return None
    
    # Determine which prompt to use
    prompt_to_use = (
        user_plugin.custom_prompt if user_plugin.custom_prompt
        else plugin.prompt
    )
    
    return {
        "id": user_plugin.id,
        "plugin_id": plugin.id,
        "name": plugin.name,
        "description": plugin.description,
        "is_default": plugin.is_default,
        "is_active": user_plugin.is_active,
        "custom_prompt": user_plugin.custom_prompt,
        "prompt_to_use": prompt_to_use,
        "created_at": user_plugin.created_at,
    }


@plugins_bp.route("", methods=["GET"])
@require_auth_cookie_or_api_key
@marshal_with(PluginListSchema, code=200)
@marshal_with(ErrorSchema, code=401)
@doc(
    tags=["Plugins"],
    description="List all plugins for current user",
    responses={
        200: {"description": "List of user plugins", "schema": PluginListSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()}
    }
)
def list_plugins():
    """List all plugins for the authenticated user.
    
    Returns both active and inactive plugins.
    
    Returns:
        - 200: PluginListSchema with all user plugins
        - 401: Unauthorized
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        all_plugins = PluginService.get_all_plugins_for_user(user_id)
        
        return {
            "plugins": all_plugins,
            "total": len(all_plugins)
        }
    
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(PluginCreateSchema, location="json")
@marshal_with(UserPluginSchema, code=201)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@doc(
    tags=["Plugins"],
    description="Create a new custom plugin",
    responses={
        201: {"description": "Plugin created", "schema": UserPluginSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()}
    }
)
def create_plugin(name, description, prompt):
    """Create a new custom plugin for the authenticated user.
    
    Args:
        name: Plugin name (1-255 chars, required)
        description: Plugin description (required)
        prompt: Evaluation prompt (required)
    
    Returns:
        - 201: UserPluginSchema for the created plugin
        - 400: Validation error
        - 401: Unauthorized
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        result = PluginService.create_custom_plugin(
            user_id=user_id,
            name=name,
            description=description,
            prompt=prompt,
        )
        
        # Fetch full response including computed fields
        response = _build_user_plugin_response(UUID(result["id"]), user_id)
        if not response:
            return {"error": "Failed to retrieve created plugin"}, 500
        
        return response, 201
    
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("/<plugin_id>", methods=["GET"])
@require_auth_cookie_or_api_key
@marshal_with(UserPluginSchema, code=200)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Plugins"],
    description="Get a single plugin with user status",
    responses={
        200: {"description": "Plugin details", "schema": UserPluginSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Plugin not found", "schema": ErrorSchema()}
    }
)
def get_plugin(plugin_id):
    """Get details of a specific plugin for the authenticated user.
    
    Args:
        plugin_id: UUID of the plugin
    
    Returns:
        - 200: UserPluginSchema with plugin details
        - 401: Unauthorized
        - 404: Plugin not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            plugin_uuid = UUID(plugin_id)
        except (ValueError, TypeError):
            return {"error": "Invalid plugin ID format"}, 400
        
        response = _build_user_plugin_response(plugin_uuid, user_id)
        if not response:
            return {"error": "Plugin not found"}, 404
        
        return response
    
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("/<plugin_id>", methods=["PUT"])
@require_auth_cookie_or_api_key
@use_kwargs(PluginUpdateSchema, location="json")
@marshal_with(UserPluginSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Plugins"],
    description="Update a custom plugin",
    responses={
        200: {"description": "Plugin updated", "schema": UserPluginSchema()},
        400: {"description": "Bad request - validation error or default plugin", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - cannot update default plugin", "schema": ErrorSchema()},
        404: {"description": "Plugin not found", "schema": ErrorSchema()}
    }
)
def update_plugin(plugin_id, name=None, description=None, prompt=None):
    """Update a custom plugin (name, description, or prompt).
    
    Cannot update default system plugins.
    
    Args:
        plugin_id: UUID of the plugin
        name: New plugin name (optional)
        description: New plugin description (optional)
        prompt: New evaluation prompt (optional)
    
    Returns:
        - 200: Updated UserPluginSchema
        - 400: Validation error or trying to update default plugin
        - 401: Unauthorized
        - 403: Cannot update default plugin
        - 404: Plugin not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            plugin_uuid = UUID(plugin_id)
        except (ValueError, TypeError):
            return {"error": "Invalid plugin ID format"}, 400
        
        # Check if this is a default plugin before updating
        from repositories.plugin_repository import PluginRepository
        plugin = PluginRepository.get_plugin(plugin_uuid)
        if not plugin:
            return {"error": "Plugin not found"}, 404
        
        if plugin.is_default:
            return {"error": "Cannot update default plugins"}, 403
        
        PluginService.update_custom_plugin(
            user_id=user_id,
            plugin_id=plugin_uuid,
            name=name,
            description=description,
            prompt=prompt,
        )
        
        response = _build_user_plugin_response(plugin_uuid, user_id)
        if not response:
            return {"error": "Failed to retrieve updated plugin"}, 500
        
        return response
    
    except PluginDeletionError as e:
        return {"error": str(e)}, 403
    except UserPluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except PluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("/<plugin_id>", methods=["DELETE"])
@require_auth_cookie_or_api_key
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Plugins"],
    description="Delete a custom plugin",
    responses={
        204: {"description": "Plugin deleted"},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - cannot delete default plugin", "schema": ErrorSchema()},
        404: {"description": "Plugin not found", "schema": ErrorSchema()}
    }
)
def delete_plugin(plugin_id):
    """Delete a custom plugin.
    
    Cannot delete default system plugins.
    
    Args:
        plugin_id: UUID of the plugin
    
    Returns:
        - 204: No Content (success)
        - 401: Unauthorized
        - 403: Cannot delete default plugin
        - 404: Plugin not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            plugin_uuid = UUID(plugin_id)
        except (ValueError, TypeError):
            return {"error": "Invalid plugin ID format"}, 400
        
        # Check if this is a default plugin before deleting
        from repositories.plugin_repository import PluginRepository
        plugin = PluginRepository.get_plugin(plugin_uuid)
        if not plugin:
            return {"error": "Plugin not found"}, 404
        
        if plugin.is_default:
            return {"error": "Cannot delete default plugins"}, 403
        
        PluginService.delete_custom_plugin(
            user_id=user_id,
            plugin_id=plugin_uuid,
        )
        
        return "", 204
    
    except PluginDeletionError as e:
        return {"error": str(e)}, 403
    except UserPluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except PluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("/<plugin_id>/activate", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(ActivatePluginSchema, location="json")
@marshal_with(UserPluginSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Plugins"],
    description="Activate or deactivate an plugin for current user",
    responses={
        200: {"description": "Plugin activation updated", "schema": UserPluginSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Plugin not found or user doesn't have this plugin", "schema": ErrorSchema()}
    }
)
def activate_plugin(plugin_id, is_active):
    """Toggle plugin activation status for the authenticated user.
    
    Args:
        plugin_id: UUID of the plugin
        is_active: Boolean - True to activate, False to deactivate
    
    Returns:
        - 200: Updated UserPluginSchema
        - 400: Validation error
        - 401: Unauthorized
        - 404: Plugin not found or user doesn't have this plugin
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            plugin_uuid = UUID(plugin_id)
        except (ValueError, TypeError):
            return {"error": "Invalid plugin ID format"}, 400
        
        if is_active:
            PluginService.activate_plugin(user_id=user_id, plugin_id=plugin_uuid)
        else:
            PluginService.deactivate_plugin(user_id=user_id, plugin_id=plugin_uuid)
        
        response = _build_user_plugin_response(plugin_uuid, user_id)
        if not response:
            return {"error": "Plugin not found"}, 404
        
        return response
    
    except UserPluginNotFoundError:
        return {"error": "Plugin not found or user doesn't have this plugin"}, 404
    except PluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@plugins_bp.route("/<plugin_id>/override-prompt", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(OverridePromptSchema, location="json")
@marshal_with(UserPluginSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Plugins"],
    description="Override or revert prompt for an plugin",
    responses={
        200: {"description": "Prompt override updated", "schema": UserPluginSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Plugin not found or user doesn't have this plugin", "schema": ErrorSchema()}
    }
)
def override_prompt(plugin_id, custom_prompt=None):
    """Override or revert the prompt for an plugin.
    
    Pass custom_prompt=null to revert to default prompt.
    
    Args:
        plugin_id: UUID of the plugin
        custom_prompt: Custom prompt string, or None/null to revert
    
    Returns:
        - 200: Updated UserPluginSchema
        - 400: Validation error
        - 401: Unauthorized
        - 404: Plugin not found or user doesn't have this plugin
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            plugin_uuid = UUID(plugin_id)
        except (ValueError, TypeError):
            return {"error": "Invalid plugin ID format"}, 400
        
        PluginService.override_prompt(
            user_id=user_id,
            plugin_id=plugin_uuid,
            custom_prompt=custom_prompt,
        )
        
        response = _build_user_plugin_response(plugin_uuid, user_id)
        if not response:
            return {"error": "Plugin not found"}, 404
        
        return response
    
    except UserPluginNotFoundError:
        return {"error": "Plugin not found or user doesn't have this plugin"}, 404
    except PluginNotFoundError:
        return {"error": "Plugin not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500
