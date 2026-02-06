"""Aspect service layer - business logic for aspect management."""

from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from repositories.aspect_repository import AspectRepository, UserAspectRepository
from models.aspect import Aspect, UserAspect
from services.exceptions import (
    AspectNotFoundError,
    AspectDeletionError,
    UserAspectNotFoundError,
    DuplicateAspectError,
)


# Default aspects to seed for new users
DEFAULT_ASPECTS = [
    {
        "name": "Code Availability",
        "description": "Whether the code is publicly available and accessible.",
        "prompt": "Is the code for this paper publicly available? Check for GitHub repos, supplementary materials, or data repositories.",
        "is_default": True,
    },
    {
        "name": "Dependency Documentation",
        "description": "Whether all dependencies are clearly documented.",
        "prompt": "Are all software dependencies and versions clearly documented? Check for requirements.txt, setup.py, or environment files.",
        "is_default": True,
    },
    {
        "name": "Reproducibility",
        "description": "Whether the results can be reproduced with the provided materials.",
        "prompt": "Can the results be reproduced using the provided code and data? Are there sufficient details to understand the workflow?",
        "is_default": True,
    },
]


class AspectService:
    """Business logic for aspect management."""
    
    @staticmethod
    def get_or_create_default_aspects(user_id: Union[int, UUID]) -> None:
        """Seed default aspects for a user on first login (idempotent)."""
        for aspect_data in DEFAULT_ASPECTS:
            # Get or create the global default aspect
            default_aspects = AspectRepository.get_default_aspects()
            aspect_exists = any(
                a.name == aspect_data["name"] for a in default_aspects
            )
            
            if aspect_exists:
                aspect = next(
                    a for a in default_aspects if a.name == aspect_data["name"]
                )
            else:
                aspect = AspectRepository.create_aspect(**aspect_data)
            
            # Create user aspect if it doesn't exist
            existing = UserAspectRepository.get_user_aspect(
                user_id, aspect.id
            )
            if not existing:
                UserAspectRepository.create_user_aspect(
                    user_id, aspect.id, custom_prompt=None
                )
    
    @staticmethod
    def get_all_aspects_for_user(user_id: Union[int, UUID]) -> List[Dict[str, Any]]:
        """Get all aspects for user with their settings.
        
        Returns list of dicts with: {id, name, description, is_default, is_active, custom_prompt}
        """
        import sys
        
        # Ensure default aspects are seeded for this user
        try:
            AspectService.get_or_create_default_aspects(user_id)
        except Exception as e:
            print(f"ERROR seeding default aspects: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        
        user_aspects = UserAspectRepository.get_user_aspects(user_id)
        results = []
        
        for user_aspect in user_aspects:
            if user_aspect.deleted_at:
                continue  # Skip soft-deleted aspects
            
            aspect = user_aspect.aspect_id  # Peewee FK auto-resolves
            results.append({
                "id": str(aspect.id),
                "name": aspect.name,
                "description": aspect.description,
                "is_default": aspect.is_default,
                "is_active": user_aspect.is_active,
                "custom_prompt": user_aspect.custom_prompt,
            })
        
        return sorted(results, key=lambda x: x["name"])
    
    @staticmethod
    def create_custom_aspect(
        user_id: Union[int, UUID],
        name: str,
        description: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Create a custom aspect for a user.
        
        Creates both the global Aspect and UserAspect entry.
        """
        # Create global aspect (not default)
        aspect = AspectRepository.create_aspect(
            name=name,
            description=description,
            prompt=prompt,
            is_default=False,
        )
        
        # Create user aspect entry
        UserAspectRepository.create_user_aspect(
            user_id=user_id,
            aspect_id=aspect.id,
            custom_prompt=None,
        )
        
        return {
            "id": str(aspect.id),
            "name": aspect.name,
            "description": aspect.description,
            "is_default": aspect.is_default,
            "is_active": True,
            "custom_prompt": None,
        }
    
    @staticmethod
    def update_custom_aspect(
        user_id: Union[int, UUID],
        aspect_id: Union[str, UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a custom aspect.
        
        Only non-default aspects can be updated.
        """
        aspect = AspectRepository.get_aspect(aspect_id)
        if not aspect:
            raise AspectNotFoundError(f"Aspect {aspect_id} not found")
        
        if aspect.is_default:
            raise AspectDeletionError("Cannot update default aspects")
        
        # Verify user has this aspect
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            raise UserAspectNotFoundError(
                f"User does not have aspect {aspect_id}"
            )
        
        # Update global aspect
        updated_aspect = AspectRepository.update_aspect(
            aspect_id,
            name=name,
            description=description,
            prompt=prompt,
        )
        
        return {
            "id": str(updated_aspect.id),
            "name": updated_aspect.name,
            "description": updated_aspect.description,
            "is_default": updated_aspect.is_default,
            "is_active": user_aspect.is_active,
            "custom_prompt": user_aspect.custom_prompt,
        }
    
    @staticmethod
    def delete_custom_aspect(user_id: Union[int, UUID], aspect_id: Union[str, UUID]) -> None:
        """Delete a custom aspect.
        
        Only non-default aspects can be deleted.
        """
        aspect = AspectRepository.get_aspect(aspect_id)
        if not aspect:
            raise AspectNotFoundError(f"Aspect {aspect_id} not found")
        
        if aspect.is_default:
            raise AspectDeletionError("Cannot delete default aspects")
        
        # Verify user has this aspect
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            raise UserAspectNotFoundError(
                f"User does not have aspect {aspect_id}"
            )
        
        # Soft delete user aspect
        UserAspectRepository.delete_user_aspect(user_id, aspect_id)
    
    @staticmethod
    def activate_aspect(user_id: Union[int, UUID], aspect_id: Union[str, UUID]) -> None:
        """Activate an aspect for a user."""
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            raise UserAspectNotFoundError(
                f"User does not have aspect {aspect_id}"
            )
        
        UserAspectRepository.update_user_aspect(
            user_id, aspect_id, is_active=True
        )
    
    @staticmethod
    def deactivate_aspect(user_id: Union[int, UUID], aspect_id: Union[str, UUID]) -> None:
        """Deactivate an aspect for a user."""
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            raise UserAspectNotFoundError(
                f"User does not have aspect {aspect_id}"
            )
        
        UserAspectRepository.update_user_aspect(
            user_id, aspect_id, is_active=False
        )
    
    @staticmethod
    def override_prompt(
        user_id: Union[int, UUID],
        aspect_id: Union[str, UUID],
        custom_prompt: str,
    ) -> None:
        """Override the prompt for a user's aspect."""
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            raise UserAspectNotFoundError(
                f"User does not have aspect {aspect_id}"
            )
        
        UserAspectRepository.update_user_aspect(
            user_id, aspect_id, custom_prompt=custom_prompt
        )
    
    @staticmethod
    def get_active_aspects_for_evaluation(
        user_id: Union[int, UUID],
    ) -> List[Dict[str, str]]:
        """Get active aspects ready for evaluation.
        
        Returns list of dicts with: {id, name, description, prompt_to_use}
        where prompt_to_use is custom_prompt if set, else default prompt.
        """
        active_aspects = UserAspectRepository.get_active_aspects(user_id)
        results = []
        
        for aspect in active_aspects:
            # Get the user's aspect settings
            user_aspect = UserAspectRepository.get_user_aspect(
                user_id, aspect.id
            )
            
            # Use custom prompt if set, otherwise use default
            prompt_to_use = (
                user_aspect.custom_prompt
                if user_aspect.custom_prompt
                else aspect.prompt
            )
            
            results.append({
                "id": str(aspect.id),
                "name": aspect.name,
                "description": aspect.description,
                "prompt_to_use": prompt_to_use,
            })
        
        return sorted(results, key=lambda x: x["name"])
