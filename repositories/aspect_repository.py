"""Repository layer for Aspect and UserAspect models."""

from typing import Optional, List
from uuid import UUID

from models.aspect import Aspect, UserAspect
from models.database import User


class AspectRepository:
    """Data access layer for Aspect model."""
    
    @staticmethod
    def get_aspect(aspect_id: UUID) -> Optional[Aspect]:
        """Get aspect by ID."""
        try:
            return Aspect.get_by_id(aspect_id)
        except Aspect.DoesNotExist:
            return None
    
    @staticmethod
    def get_all_aspects() -> List[Aspect]:
        """Get all aspects."""
        try:
            return list(Aspect.select().order_by(Aspect.created_at))
        except Exception:
            return []
    
    @staticmethod
    def get_default_aspects() -> List[Aspect]:
        """Get all default aspects."""
        try:
            return list(
                Aspect.select()
                .where(Aspect.is_default == True)
                .order_by(Aspect.created_at)
            )
        except Exception:
            return []
    
    @staticmethod
    def create_aspect(
        name: str,
        description: str,
        prompt: str,
        is_default: bool = False
    ) -> Aspect:
        """Create a new aspect."""
        return Aspect.create(
            name=name,
            description=description,
            prompt=prompt,
            is_default=is_default
        )
    
    @staticmethod
    def update_aspect(
        aspect_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Optional[Aspect]:
        """Update aspect (name, description, prompt only)."""
        aspect = AspectRepository.get_aspect(aspect_id)
        if not aspect:
            return None
        
        if name is not None:
            aspect.name = name
        if description is not None:
            aspect.description = description
        if prompt is not None:
            aspect.prompt = prompt
        
        aspect.save()
        return aspect
    
    @staticmethod
    def delete_aspect(aspect_id: UUID) -> bool:
        """Delete aspect (only if NOT is_default)."""
        from services.exceptions import AspectDeletionError
        
        aspect = AspectRepository.get_aspect(aspect_id)
        if not aspect:
            return False
        
        if aspect.is_default:
            raise AspectDeletionError("Cannot delete default aspect")
        
        aspect.delete_instance()
        return True


class UserAspectRepository:
    """Data access layer for UserAspect model."""
    
    @staticmethod
    def get_user_aspects(user_id: UUID) -> List[UserAspect]:
        """Get all aspects for a user (including deleted)."""
        try:
            return list(
                UserAspect.select()
                .where(UserAspect.user_id == user_id)
                .order_by(UserAspect.created_at)
            )
        except Exception:
            return []
    
    @staticmethod
    def get_active_aspects(user_id: UUID) -> List[Aspect]:
        """Get only active aspects for a user (JOIN with Aspect)."""
        try:
            return list(
                Aspect.select()
                .join(UserAspect)
                .where(
                    (UserAspect.user_id == user_id) &
                    (UserAspect.is_active == True) &
                    (UserAspect.deleted_at.is_null())
                )
                .order_by(Aspect.created_at)
            )
        except Exception:
            return []
    
    @staticmethod
    def get_user_aspect(
        user_id: UUID,
        aspect_id: UUID
    ) -> Optional[UserAspect]:
        """Get specific user aspect."""
        try:
            return UserAspect.get(
                (UserAspect.user_id == user_id) &
                (UserAspect.aspect_id == aspect_id)
            )
        except UserAspect.DoesNotExist:
            return None
    
    @staticmethod
    def create_user_aspect(
        user_id: UUID,
        aspect_id: UUID,
        custom_prompt: Optional[str] = None
    ) -> UserAspect:
        """Create user aspect entry."""
        return UserAspect.create(
            user_id=user_id,
            aspect_id=aspect_id,
            custom_prompt=custom_prompt,
            is_active=True
        )
    
    @staticmethod
    def update_user_aspect(
        user_id: UUID,
        aspect_id: UUID,
        is_active: Optional[bool] = None,
        custom_prompt: Optional[str] = None
    ) -> Optional[UserAspect]:
        """Update user aspect (is_active and/or custom_prompt)."""
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            return None
        
        if is_active is not None:
            user_aspect.is_active = is_active
        if custom_prompt is not None:
            user_aspect.custom_prompt = custom_prompt
        
        user_aspect.save()
        return user_aspect
    
    @staticmethod
    def delete_user_aspect(user_id: UUID, aspect_id: UUID) -> bool:
        """Soft delete user aspect (mark deleted_at)."""
        from datetime import datetime
        
        user_aspect = UserAspectRepository.get_user_aspect(user_id, aspect_id)
        if not user_aspect:
            return False
        
        user_aspect.deleted_at = datetime.now()
        user_aspect.save()
        return True
