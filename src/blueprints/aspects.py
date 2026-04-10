"""API blueprint for aspect management endpoints.

This module provides REST API endpoints for managing reproducibility aspects,
including CRUD operations, activation/deactivation, and prompt overrides.
"""

from uuid import UUID
from flask import Blueprint, request, jsonify
from flask_apispec import doc, use_kwargs, marshal_with

from utils.decorators import require_auth_cookie_or_api_key, get_current_user_id
from schemas.aspect import (
    AspectCreateSchema, AspectUpdateSchema, ActivateAspectSchema,
    OverridePromptSchema, UserAspectSchema, AspectListSchema, AspectSchema
)
from schemas.common import ErrorSchema
from services.aspect_service import AspectService
from services.exceptions import (
    AspectNotFoundError, AspectDeletionError, UserAspectNotFoundError
)

aspects_bp = Blueprint('aspects', __name__, url_prefix='/api/aspects')


def _build_user_aspect_response(aspect_id, user_id):
    """Helper to build a UserAspectSchema response.
    
    Args:
        aspect_id: UUID of the aspect
        user_id: UUID of the user
        
    Returns:
        Dict matching UserAspectSchema or None if not found
    """
    from repositories.aspect_repository import AspectRepository, UserAspectRepository
    
    aspect = AspectRepository.get_aspect(aspect_id)
    if not aspect:
        return None
    
    user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
    if not user_aspect:
        return None
    
    # Determine which prompt to use
    prompt_to_use = (
        user_aspect.custom_prompt if user_aspect.custom_prompt
        else aspect.prompt
    )
    
    return {
        "id": user_aspect.id,
        "aspect_id": aspect.id,
        "name": aspect.name,
        "description": aspect.description,
        "is_default": aspect.is_default,
        "is_active": user_aspect.is_active,
        "custom_prompt": user_aspect.custom_prompt,
        "prompt_to_use": prompt_to_use,
        "created_at": user_aspect.created_at,
    }


@aspects_bp.route("", methods=["GET"])
@require_auth_cookie_or_api_key
@marshal_with(AspectListSchema, code=200)
@marshal_with(ErrorSchema, code=401)
@doc(
    tags=["Aspects"],
    description="List all aspects for current user",
    responses={
        200: {"description": "List of user aspects", "schema": AspectListSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()}
    }
)
def list_aspects():
    """List all aspects for the authenticated user.
    
    Returns both active and inactive aspects.
    
    Returns:
        - 200: AspectListSchema with all user aspects
        - 401: Unauthorized
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        all_aspects = AspectService.get_all_aspects_for_user(user_id)
        
        return {
            "aspects": all_aspects,
            "total": len(all_aspects)
        }
    
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(AspectCreateSchema, location="json")
@marshal_with(UserAspectSchema, code=201)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@doc(
    tags=["Aspects"],
    description="Create a new custom aspect",
    responses={
        201: {"description": "Aspect created", "schema": UserAspectSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()}
    }
)
def create_aspect(name, description, prompt):
    """Create a new custom aspect for the authenticated user.
    
    Args:
        name: Aspect name (1-255 chars, required)
        description: Aspect description (required)
        prompt: Evaluation prompt (required)
    
    Returns:
        - 201: UserAspectSchema for the created aspect
        - 400: Validation error
        - 401: Unauthorized
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        result = AspectService.create_custom_aspect(
            user_id=user_id,
            name=name,
            description=description,
            prompt=prompt,
        )
        
        # Fetch full response including computed fields
        response = _build_user_aspect_response(UUID(result["id"]), user_id)
        if not response:
            return {"error": "Failed to retrieve created aspect"}, 500
        
        return response, 201
    
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("/<aspect_id>", methods=["GET"])
@require_auth_cookie_or_api_key
@marshal_with(UserAspectSchema, code=200)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Aspects"],
    description="Get a single aspect with user status",
    responses={
        200: {"description": "Aspect details", "schema": UserAspectSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Aspect not found", "schema": ErrorSchema()}
    }
)
def get_aspect(aspect_id):
    """Get details of a specific aspect for the authenticated user.
    
    Args:
        aspect_id: UUID of the aspect
    
    Returns:
        - 200: UserAspectSchema with aspect details
        - 401: Unauthorized
        - 404: Aspect not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            aspect_uuid = UUID(aspect_id)
        except (ValueError, TypeError):
            return {"error": "Invalid aspect ID format"}, 400
        
        response = _build_user_aspect_response(aspect_uuid, user_id)
        if not response:
            return {"error": "Aspect not found"}, 404
        
        return response
    
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("/<aspect_id>", methods=["PUT"])
@require_auth_cookie_or_api_key
@use_kwargs(AspectUpdateSchema, location="json")
@marshal_with(UserAspectSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Aspects"],
    description="Update a custom aspect",
    responses={
        200: {"description": "Aspect updated", "schema": UserAspectSchema()},
        400: {"description": "Bad request - validation error or default aspect", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - cannot update default aspect", "schema": ErrorSchema()},
        404: {"description": "Aspect not found", "schema": ErrorSchema()}
    }
)
def update_aspect(aspect_id, name=None, description=None, prompt=None):
    """Update a custom aspect (name, description, or prompt).
    
    Cannot update default system aspects.
    
    Args:
        aspect_id: UUID of the aspect
        name: New aspect name (optional)
        description: New aspect description (optional)
        prompt: New evaluation prompt (optional)
    
    Returns:
        - 200: Updated UserAspectSchema
        - 400: Validation error or trying to update default aspect
        - 401: Unauthorized
        - 403: Cannot update default aspect
        - 404: Aspect not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            aspect_uuid = UUID(aspect_id)
        except (ValueError, TypeError):
            return {"error": "Invalid aspect ID format"}, 400
        
        # Check if this is a default aspect before updating
        from repositories.aspect_repository import AspectRepository
        aspect = AspectRepository.get_aspect(aspect_uuid)
        if not aspect:
            return {"error": "Aspect not found"}, 404
        
        if aspect.is_default:
            return {"error": "Cannot update default aspects"}, 403
        
        AspectService.update_custom_aspect(
            user_id=user_id,
            aspect_id=aspect_uuid,
            name=name,
            description=description,
            prompt=prompt,
        )
        
        response = _build_user_aspect_response(aspect_uuid, user_id)
        if not response:
            return {"error": "Failed to retrieve updated aspect"}, 500
        
        return response
    
    except AspectDeletionError as e:
        return {"error": str(e)}, 403
    except UserAspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except AspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("/<aspect_id>", methods=["DELETE"])
@require_auth_cookie_or_api_key
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=403)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Aspects"],
    description="Delete a custom aspect",
    responses={
        204: {"description": "Aspect deleted"},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        403: {"description": "Forbidden - cannot delete default aspect", "schema": ErrorSchema()},
        404: {"description": "Aspect not found", "schema": ErrorSchema()}
    }
)
def delete_aspect(aspect_id):
    """Delete a custom aspect.
    
    Cannot delete default system aspects.
    
    Args:
        aspect_id: UUID of the aspect
    
    Returns:
        - 204: No Content (success)
        - 401: Unauthorized
        - 403: Cannot delete default aspect
        - 404: Aspect not found
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            aspect_uuid = UUID(aspect_id)
        except (ValueError, TypeError):
            return {"error": "Invalid aspect ID format"}, 400
        
        # Check if this is a default aspect before deleting
        from repositories.aspect_repository import AspectRepository
        aspect = AspectRepository.get_aspect(aspect_uuid)
        if not aspect:
            return {"error": "Aspect not found"}, 404
        
        if aspect.is_default:
            return {"error": "Cannot delete default aspects"}, 403
        
        AspectService.delete_custom_aspect(
            user_id=user_id,
            aspect_id=aspect_uuid,
        )
        
        return "", 204
    
    except AspectDeletionError as e:
        return {"error": str(e)}, 403
    except UserAspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except AspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("/<aspect_id>/activate", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(ActivateAspectSchema, location="json")
@marshal_with(UserAspectSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Aspects"],
    description="Activate or deactivate an aspect for current user",
    responses={
        200: {"description": "Aspect activation updated", "schema": UserAspectSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Aspect not found or user doesn't have this aspect", "schema": ErrorSchema()}
    }
)
def activate_aspect(aspect_id, is_active):
    """Toggle aspect activation status for the authenticated user.
    
    Args:
        aspect_id: UUID of the aspect
        is_active: Boolean - True to activate, False to deactivate
    
    Returns:
        - 200: Updated UserAspectSchema
        - 400: Validation error
        - 401: Unauthorized
        - 404: Aspect not found or user doesn't have this aspect
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            aspect_uuid = UUID(aspect_id)
        except (ValueError, TypeError):
            return {"error": "Invalid aspect ID format"}, 400
        
        if is_active:
            AspectService.activate_aspect(user_id=user_id, aspect_id=aspect_uuid)
        else:
            AspectService.deactivate_aspect(user_id=user_id, aspect_id=aspect_uuid)
        
        response = _build_user_aspect_response(aspect_uuid, user_id)
        if not response:
            return {"error": "Aspect not found"}, 404
        
        return response
    
    except UserAspectNotFoundError:
        return {"error": "Aspect not found or user doesn't have this aspect"}, 404
    except AspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@aspects_bp.route("/<aspect_id>/override-prompt", methods=["POST"])
@require_auth_cookie_or_api_key
@use_kwargs(OverridePromptSchema, location="json")
@marshal_with(UserAspectSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
@marshal_with(ErrorSchema, code=404)
@doc(
    tags=["Aspects"],
    description="Override or revert prompt for an aspect",
    responses={
        200: {"description": "Prompt override updated", "schema": UserAspectSchema()},
        400: {"description": "Bad request - validation error", "schema": ErrorSchema()},
        401: {"description": "Unauthorized", "schema": ErrorSchema()},
        404: {"description": "Aspect not found or user doesn't have this aspect", "schema": ErrorSchema()}
    }
)
def override_prompt(aspect_id, custom_prompt=None):
    """Override or revert the prompt for an aspect.
    
    Pass custom_prompt=null to revert to default prompt.
    
    Args:
        aspect_id: UUID of the aspect
        custom_prompt: Custom prompt string, or None/null to revert
    
    Returns:
        - 200: Updated UserAspectSchema
        - 400: Validation error
        - 401: Unauthorized
        - 404: Aspect not found or user doesn't have this aspect
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return {"error": "Unauthorized"}, 401
        
        try:
            aspect_uuid = UUID(aspect_id)
        except (ValueError, TypeError):
            return {"error": "Invalid aspect ID format"}, 400
        
        AspectService.override_prompt(
            user_id=user_id,
            aspect_id=aspect_uuid,
            custom_prompt=custom_prompt,
        )
        
        response = _build_user_aspect_response(aspect_uuid, user_id)
        if not response:
            return {"error": "Aspect not found"}, 404
        
        return response
    
    except UserAspectNotFoundError:
        return {"error": "Aspect not found or user doesn't have this aspect"}, 404
    except AspectNotFoundError:
        return {"error": "Aspect not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500
