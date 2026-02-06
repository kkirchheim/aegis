"""Tests for AspectRepository and UserAspectRepository."""

import pytest
from uuid import UUID
from models.database import User
from models.aspect import Aspect, UserAspect
from repositories.aspect_repository import AspectRepository, UserAspectRepository
from services.exceptions import AspectDeletionError


@pytest.mark.db
class TestAspectRepository:
    """Tests for AspectRepository."""
    
    def test_create_aspect(self, app):
        """Test creating an aspect."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Test Aspect",
                description="Test Description",
                prompt="Test Prompt",
                is_default=False,
            )
            
            assert aspect.id is not None
            assert aspect.name == "Test Aspect"
            assert aspect.is_default is False
    
    def test_create_default_aspect(self, app):
        """Test creating a default aspect."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Default Aspect",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            
            assert aspect.is_default is True
    
    def test_get_aspect_by_id(self, app):
        """Test getting an aspect by ID."""
        with app.app_context():
            created = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            retrieved = AspectRepository.get_aspect(created.id)
            
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.name == "Test"
    
    def test_get_aspect_by_id_not_found(self, app):
        """Test getting a non-existent aspect returns None."""
        with app.app_context():
            from uuid import uuid4
            result = AspectRepository.get_aspect(uuid4())
            assert result is None
    
    def test_get_all_aspects(self, app):
        """Test getting all aspects."""
        with app.app_context():
            aspect1 = AspectRepository.create_aspect(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = AspectRepository.create_aspect(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            all_aspects = AspectRepository.get_all_aspects()
            
            assert len(all_aspects) >= 2
            assert any(a.id == aspect1.id for a in all_aspects)
            assert any(a.id == aspect2.id for a in all_aspects)
    
    def test_get_default_aspects(self, app):
        """Test getting only default aspects."""
        with app.app_context():
            default = AspectRepository.create_aspect(
                name="Default",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            non_default = AspectRepository.create_aspect(
                name="Non-Default",
                description="Desc",
                prompt="Prompt",
                is_default=False,
            )
            
            defaults = AspectRepository.get_default_aspects()
            
            assert any(a.id == default.id for a in defaults)
            assert not any(a.id == non_default.id for a in defaults)
    
    def test_update_aspect(self, app):
        """Test updating an aspect."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Original",
                description="Original Desc",
                prompt="Original Prompt",
            )
            
            updated = AspectRepository.update_aspect(
                aspect.id,
                name="Updated",
                description="Updated Desc",
                prompt="Updated Prompt",
            )
            
            assert updated.name == "Updated"
            assert updated.description == "Updated Desc"
            assert updated.prompt == "Updated Prompt"
    
    def test_update_aspect_partial(self, app):
        """Test updating only some fields."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Original",
                description="Original Desc",
                prompt="Original Prompt",
            )
            
            updated = AspectRepository.update_aspect(
                aspect.id,
                name="Updated",
            )
            
            assert updated.name == "Updated"
            assert updated.description == "Original Desc"
            assert updated.prompt == "Original Prompt"
    
    def test_update_aspect_not_found(self, app):
        """Test updating a non-existent aspect."""
        with app.app_context():
            from uuid import uuid4
            result = AspectRepository.update_aspect(uuid4(), name="New")
            assert result is None
    
    def test_delete_non_default_aspect(self, app):
        """Test deleting a non-default aspect succeeds."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Non-Default",
                description="Desc",
                prompt="Prompt",
                is_default=False,
            )
            
            result = AspectRepository.delete_aspect(aspect.id)
            
            assert result is True
            assert AspectRepository.get_aspect(aspect.id) is None
    
    def test_delete_default_aspect_fails(self, app):
        """Test deleting a default aspect raises AspectDeletionError."""
        with app.app_context():
            aspect = AspectRepository.create_aspect(
                name="Default",
                description="Desc",
                prompt="Prompt",
                is_default=True,
            )
            
            with pytest.raises(AspectDeletionError):
                AspectRepository.delete_aspect(aspect.id)
    
    def test_delete_non_existent_aspect(self, app):
        """Test deleting a non-existent aspect returns False."""
        with app.app_context():
            from uuid import uuid4
            result = AspectRepository.delete_aspect(uuid4())
            assert result is False
    
    def test_update_multiple_aspects_isolation(self, app):
        """Test that updating multiple aspects doesn't affect others."""
        with app.app_context():
            aspect1 = AspectRepository.create_aspect(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = AspectRepository.create_aspect(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            AspectRepository.update_aspect(aspect1.id, name="Updated 1")
            
            updated1 = AspectRepository.get_aspect(aspect1.id)
            unchanged2 = AspectRepository.get_aspect(aspect2.id)
            
            assert updated1.name == "Updated 1"
            assert unchanged2.name == "Aspect 2"


@pytest.mark.db
class TestUserAspectRepository:
    """Tests for UserAspectRepository."""
    
    def test_create_user_aspect(self, app):
        """Test creating a user aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspectRepository.create_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            assert user_aspect.user_id == user.id
            assert user_aspect.aspect_id == aspect.id
            assert user_aspect.is_active is True
    
    def test_create_user_aspect_with_custom_prompt(self, app):
        """Test creating a user aspect with custom prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspectRepository.create_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
                custom_prompt="Custom Prompt",
            )
            
            assert user_aspect.custom_prompt == "Custom Prompt"
    
    def test_get_user_aspect(self, app):
        """Test getting a specific user aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            created = UserAspectRepository.create_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            retrieved = UserAspectRepository.get_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            assert retrieved is not None
            assert retrieved.id == created.id
    
    def test_get_user_aspect_not_found(self, app):
        """Test getting a non-existent user aspect."""
        with app.app_context():
            from uuid import uuid4
            result = UserAspectRepository.get_user_aspect(uuid4(), uuid4())
            assert result is None
    
    def test_get_user_aspects(self, app):
        """Test getting all aspects for a user."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            aspect1 = AspectRepository.create_aspect(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = AspectRepository.create_aspect(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect1.id)
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect2.id)
            
            user_aspects = UserAspectRepository.get_user_aspects(user.id)
            
            assert len(user_aspects) == 2
            assert any(ua.aspect_id == aspect1.id for ua in user_aspects)
            assert any(ua.aspect_id == aspect2.id for ua in user_aspects)
    
    def test_get_active_aspects(self, app):
        """Test getting only active aspects."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            aspect1 = AspectRepository.create_aspect(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = AspectRepository.create_aspect(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            ua1 = UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect1.id)
            ua2 = UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect2.id)
            
            # Deactivate aspect2
            UserAspectRepository.update_user_aspect(user.id, aspect2.id, is_active=False)
            
            active = UserAspectRepository.get_active_aspects(user.id)
            
            assert len(active) == 1
            assert active[0].id == aspect1.id
    
    def test_get_active_aspects_excludes_soft_deleted(self, app):
        """Test that soft-deleted aspects are excluded from active."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect.id)
            
            # Soft delete
            UserAspectRepository.delete_user_aspect(user.id, aspect.id)
            
            active = UserAspectRepository.get_active_aspects(user.id)
            
            assert len(active) == 0
    
    def test_update_user_aspect_is_active(self, app):
        """Test updating is_active flag."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect.id)
            
            updated = UserAspectRepository.update_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
                is_active=False,
            )
            
            assert updated.is_active is False
    
    def test_update_user_aspect_custom_prompt(self, app):
        """Test updating custom_prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect.id)
            
            updated = UserAspectRepository.update_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
                custom_prompt="Custom",
            )
            
            assert updated.custom_prompt == "Custom"
    
    def test_update_user_aspect_both_fields(self, app):
        """Test updating both is_active and custom_prompt."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect.id)
            
            updated = UserAspectRepository.update_user_aspect(
                user_id=user.id,
                aspect_id=aspect.id,
                is_active=False,
                custom_prompt="Custom",
            )
            
            assert updated.is_active is False
            assert updated.custom_prompt == "Custom"
    
    def test_delete_user_aspect(self, app):
        """Test soft deleting a user aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            UserAspectRepository.create_user_aspect(user_id=user.id, aspect_id=aspect.id)
            
            result = UserAspectRepository.delete_user_aspect(user.id, aspect.id)
            
            assert result is True
            
            # Check that deleted_at is set
            user_aspect = UserAspectRepository.get_user_aspect(user.id, aspect.id)
            assert user_aspect.deleted_at is not None
    
    def test_delete_user_aspect_not_found(self, app):
        """Test deleting a non-existent user aspect."""
        with app.app_context():
            from uuid import uuid4
            result = UserAspectRepository.delete_user_aspect(uuid4(), uuid4())
            assert result is False
    
    def test_multiple_users_isolated(self, app):
        """Test that multiple users have isolated aspect states."""
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
            
            aspect = AspectRepository.create_aspect(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            ua1 = UserAspectRepository.create_user_aspect(user_id=user1.id, aspect_id=aspect.id)
            ua2 = UserAspectRepository.create_user_aspect(user_id=user2.id, aspect_id=aspect.id)
            
            # Update user1's aspect
            UserAspectRepository.update_user_aspect(
                user_id=user1.id,
                aspect_id=aspect.id,
                is_active=False,
            )
            
            # Check user2 is unaffected
            user2_aspect = UserAspectRepository.get_user_aspect(user2.id, aspect.id)
            assert user2_aspect.is_active is True
