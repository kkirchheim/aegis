"""Tests for AspectService."""

import pytest
from uuid import UUID
from models.database import User
from models.aspect import Aspect
from services.aspect_service import AspectService, DEFAULT_ASPECTS
from repositories.aspect_repository import AspectRepository, UserAspectRepository
from services.exceptions import (
    AspectNotFoundError,
    AspectDeletionError,
    UserAspectNotFoundError,
    DuplicateAspectError,
)


@pytest.mark.db
class TestAspectService:
    """Tests for AspectService."""
    
    def test_seed_defaults_on_first_user(self, app):
        """Test seeding default aspects for a new user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            AspectService.get_or_create_default_aspects(user.id)
            
            aspects = AspectService.get_all_aspects_for_user(user.id)
            
            # Should have 3 default aspects
            assert len(aspects) == 3
            assert all(a["is_default"] is True for a in aspects)
    
    def test_seed_defaults_idempotent(self, app):
        """Test that seeding defaults is idempotent."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed twice
            AspectService.get_or_create_default_aspects(user.id)
            AspectService.get_or_create_default_aspects(user.id)
            
            # Should still have 3 (not 6)
            aspects = AspectService.get_all_aspects_for_user(user.id)
            assert len(aspects) == 3
    
    def test_get_all_aspects_for_user(self, app):
        """Test getting all aspects for a user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            # Add custom aspect
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom Aspect",
                description="Custom Desc",
                prompt="Custom Prompt",
            )
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            
            # Should have 4 (3 default + 1 custom)
            assert len(all_aspects) == 4
            assert any(a["name"] == "Custom Aspect" for a in all_aspects)
            assert all(
                set(a.keys()) == {"id", "name", "description", "is_default", "is_active", "custom_prompt"}
                for a in all_aspects
            )
    
    def test_create_custom_aspect(self, app):
        """Test creating a custom aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            result = AspectService.create_custom_aspect(
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
    
    def test_update_custom_aspect(self, app):
        """Test updating a custom aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            result = AspectService.update_custom_aspect(
                user_id=user.id,
                aspect_id=aspect_id,
                name="Updated",
                description="Updated Desc",
                prompt="Updated Prompt",
            )
            
            assert result["name"] == "Updated"
            assert result["description"] == "Updated Desc"
    
    def test_update_default_aspect_fails(self, app):
        """Test that updating a default aspect raises error."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            default_aspect = next(a for a in all_aspects if a["is_default"])
            
            with pytest.raises(AspectDeletionError):
                AspectService.update_custom_aspect(
                    user_id=user.id,
                    aspect_id=UUID(default_aspect["id"]),
                    name="New Name",
                )
    
    def test_delete_custom_aspect(self, app):
        """Test deleting a custom aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            AspectService.delete_custom_aspect(user_id=user.id, aspect_id=aspect_id)
            
            # Should be gone from user's aspects
            remaining = AspectService.get_all_aspects_for_user(user.id)
            assert not any(a["id"] == str(aspect_id) for a in remaining)
    
    def test_delete_default_aspect_fails(self, app):
        """Test that deleting a default aspect raises error."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            default_aspect = next(a for a in all_aspects if a["is_default"])
            
            with pytest.raises(AspectDeletionError):
                AspectService.delete_custom_aspect(
                    user_id=user.id,
                    aspect_id=UUID(default_aspect["id"]),
                )
    
    def test_activate_aspect(self, app):
        """Test activating an aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            # Deactivate
            AspectService.deactivate_aspect(user_id=user.id, aspect_id=aspect_id)
            
            # Activate
            AspectService.activate_aspect(user_id=user.id, aspect_id=aspect_id)
            
            aspects = AspectService.get_all_aspects_for_user(user.id)
            aspect = next(a for a in aspects if a["id"] == str(aspect_id))
            assert aspect["is_active"] is True
    
    def test_deactivate_aspect(self, app):
        """Test deactivating an aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            AspectService.deactivate_aspect(user_id=user.id, aspect_id=aspect_id)
            
            aspects = AspectService.get_all_aspects_for_user(user.id)
            aspect = next(a for a in aspects if a["id"] == str(aspect_id))
            assert aspect["is_active"] is False
    
    def test_override_prompt(self, app):
        """Test overriding a prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Original Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            AspectService.override_prompt(
                user_id=user.id,
                aspect_id=aspect_id,
                custom_prompt="Custom Prompt",
            )
            
            aspects = AspectService.get_all_aspects_for_user(user.id)
            aspect = next(a for a in aspects if a["id"] == str(aspect_id))
            assert aspect["custom_prompt"] == "Custom Prompt"
    
    def test_get_active_aspects_for_evaluation(self, app):
        """Test getting active aspects for evaluation."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            active = AspectService.get_active_aspects_for_evaluation(user.id)
            
            # Should have 3 active default aspects
            assert len(active) == 3
            assert all(
                set(a.keys()) == {"id", "name", "prompt_to_use"}
                for a in active
            )
    
    def test_get_active_aspects_uses_custom_prompt(self, app):
        """Test that custom prompt is used in evaluation."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Original Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            # Override prompt
            AspectService.override_prompt(
                user_id=user.id,
                aspect_id=aspect_id,
                custom_prompt="Custom Prompt",
            )
            
            active = AspectService.get_active_aspects_for_evaluation(user.id)
            custom_aspect = next(a for a in active if a["id"] == str(aspect_id))
            
            # Should use custom prompt
            assert custom_aspect["prompt_to_use"] == "Custom Prompt"
    
    def test_get_active_aspects_uses_default_prompt(self, app):
        """Test that default prompt is used when no custom prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom",
                description="Desc",
                prompt="Default Prompt",
            )
            
            aspect_id = UUID(custom["id"])
            
            active = AspectService.get_active_aspects_for_evaluation(user.id)
            custom_aspect = next(a for a in active if a["id"] == str(aspect_id))
            
            # Should use default prompt
            assert custom_aspect["prompt_to_use"] == "Default Prompt"
    
    def test_get_active_aspects_excludes_inactive(self, app):
        """Test that inactive aspects are excluded."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            first_aspect = all_aspects[0]
            
            # Deactivate first aspect
            AspectService.deactivate_aspect(
                user_id=user.id,
                aspect_id=UUID(first_aspect["id"]),
            )
            
            active = AspectService.get_active_aspects_for_evaluation(user.id)
            
            # Should have 2 (one deactivated)
            assert len(active) == 2
            assert not any(a["id"] == first_aspect["id"] for a in active)


@pytest.mark.db
class TestAspectServiceIntegration:
    """Integration tests for AspectService."""
    
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
            AspectService.get_or_create_default_aspects(user.id)
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            assert len(all_aspects) == 3
            
            # 3. Create custom aspect
            custom = AspectService.create_custom_aspect(
                user_id=user.id,
                name="Custom Aspect",
                description="Custom Desc",
                prompt="Custom Prompt",
            )
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            assert len(all_aspects) == 4
            
            # 4. Override prompt
            aspect_id = UUID(custom["id"])
            AspectService.override_prompt(
                user_id=user.id,
                aspect_id=aspect_id,
                custom_prompt="Overridden Prompt",
            )
            
            # 5. Get for evaluation
            active = AspectService.get_active_aspects_for_evaluation(user.id)
            custom_eval = next(a for a in active if a["id"] == str(aspect_id))
            assert custom_eval["prompt_to_use"] == "Overridden Prompt"
    
    def test_multiple_users_isolated(self, app):
        """Test that multiple users have isolated aspects."""
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
            AspectService.get_or_create_default_aspects(user1.id)
            AspectService.get_or_create_default_aspects(user2.id)
            
            # User1 creates custom aspect
            custom1 = AspectService.create_custom_aspect(
                user_id=user1.id,
                name="User1 Custom",
                description="Desc",
                prompt="Prompt",
            )
            
            # Check isolation
            user1_aspects = AspectService.get_all_aspects_for_user(user1.id)
            user2_aspects = AspectService.get_all_aspects_for_user(user2.id)
            
            assert len(user1_aspects) == 4  # 3 default + 1 custom
            assert len(user2_aspects) == 3  # 3 default only
            
            # User1's custom should not be in user2's list
            user2_ids = {UUID(a["id"]) for a in user2_aspects}
            assert UUID(custom1["id"]) not in user2_ids
    
    def test_default_aspects_cannot_be_modified_via_service(self, app):
        """Test that default aspects cannot be modified through service."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            # Seed defaults
            AspectService.get_or_create_default_aspects(user.id)
            
            all_aspects = AspectService.get_all_aspects_for_user(user.id)
            default = next(a for a in all_aspects if a["is_default"])
            default_id = UUID(default["id"])
            
            # Try to update - should fail
            with pytest.raises(AspectDeletionError):
                AspectService.update_custom_aspect(
                    user_id=user.id,
                    aspect_id=default_id,
                    name="Modified",
                )
            
            # Try to delete - should fail
            with pytest.raises(AspectDeletionError):
                AspectService.delete_custom_aspect(
                    user_id=user.id,
                    aspect_id=default_id,
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
            AspectService.get_or_create_default_aspects(user1.id)
            AspectService.get_or_create_default_aspects(user2.id)
            
            # Get first default aspect
            user1_aspects = AspectService.get_all_aspects_for_user(user1.id)
            aspect_id = UUID(user1_aspects[0]["id"])
            
            # Override for user1
            AspectService.override_prompt(
                user_id=user1.id,
                aspect_id=aspect_id,
                custom_prompt="User1 Override",
            )
            
            # User1 should have override
            user1_eval = AspectService.get_active_aspects_for_evaluation(user1.id)
            user1_aspect = next(a for a in user1_eval if a["id"] == str(aspect_id))
            assert user1_aspect["prompt_to_use"] == "User1 Override"
            
            # User2 should use default
            user2_eval = AspectService.get_active_aspects_for_evaluation(user2.id)
            user2_aspect = next(a for a in user2_eval if a["id"] == str(aspect_id))
            assert user2_aspect["prompt_to_use"] != "User1 Override"
