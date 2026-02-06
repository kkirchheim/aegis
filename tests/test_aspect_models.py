"""Tests for Aspect and UserAspect models."""

import pytest
import uuid
from datetime import datetime
from models.aspect import Aspect, UserAspect
from models.database import User, init_db


@pytest.mark.db
class TestAspectModel:
    """Tests for Aspect model."""
    
    def test_aspect_creation_with_all_fields(self, app):
        """Test creating an aspect with all fields."""
        with app.app_context():
            aspect = Aspect.create(
                name="Test Aspect",
                description="Test Description",
                prompt="Test Prompt",
                is_default=True,
            )
            
            assert aspect.id is not None
            assert aspect.name == "Test Aspect"
            assert aspect.description == "Test Description"
            assert aspect.prompt == "Test Prompt"
            assert aspect.is_default is True
            assert isinstance(aspect.created_at, datetime)
            assert isinstance(aspect.updated_at, datetime)
    
    def test_aspect_creation_default_is_false(self, app):
        """Test that is_default defaults to False."""
        with app.app_context():
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            assert aspect.is_default is False
    
    def test_aspect_timestamps_auto_set(self, app):
        """Test that timestamps are automatically set."""
        with app.app_context():
            before = datetime.now()
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            after = datetime.now()
            
            assert before <= aspect.created_at <= after
            assert before <= aspect.updated_at <= after
    
    def test_aspect_multiple_creation(self, app):
        """Test creating multiple aspects."""
        with app.app_context():
            aspect1 = Aspect.create(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = Aspect.create(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            assert aspect1.id != aspect2.id
            assert aspect1.name != aspect2.name


@pytest.mark.db
class TestUserAspectModel:
    """Tests for UserAspect model."""
    
    def test_user_aspect_creation(self, app):
        """Test creating a user aspect."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect.id,
                is_active=True,
            )
            
            assert user_aspect.id is not None
            assert user_aspect.user_id == user.id
            assert user_aspect.aspect_id == aspect.id
            assert user_aspect.is_active is True
            assert user_aspect.custom_prompt is None
            assert user_aspect.deleted_at is None
            assert isinstance(user_aspect.created_at, datetime)
            assert isinstance(user_aspect.updated_at, datetime)
    
    def test_user_aspect_custom_prompt_nullable(self, app):
        """Test that custom_prompt is nullable."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect.id,
                custom_prompt=None,
            )
            
            assert user_aspect.custom_prompt is None
            
            # Update with a custom prompt
            user_aspect.custom_prompt = "Custom Prompt"
            user_aspect.save()
            
            # Refresh from DB
            user_aspect = UserAspect.get_by_id(user_aspect.id)
            assert user_aspect.custom_prompt == "Custom Prompt"
    
    def test_user_aspect_unique_constraint(self, app):
        """Test that unique(user_id, aspect_id) constraint is enforced."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            # Create first user aspect
            UserAspect.create(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            # Try to create duplicate - should raise IntegrityError
            with pytest.raises(Exception):  # Peewee raises IntegrityError
                UserAspect.create(
                    user_id=user.id,
                    aspect_id=aspect.id,
                )
    
    def test_user_aspect_multiple_per_user(self, app):
        """Test that a user can have multiple aspects."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            
            aspect1 = Aspect.create(
                name="Aspect 1",
                description="Desc 1",
                prompt="Prompt 1",
            )
            aspect2 = Aspect.create(
                name="Aspect 2",
                description="Desc 2",
                prompt="Prompt 2",
            )
            
            ua1 = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect1.id,
            )
            ua2 = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect2.id,
            )
            
            assert ua1.id != ua2.id
            assert ua1.aspect_id != ua2.aspect_id
    
    def test_user_aspect_is_active_default(self, app):
        """Test that is_active defaults to True."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            assert user_aspect.is_active is True
    
    def test_user_aspect_soft_delete(self, app):
        """Test that deleted_at marks soft delete."""
        with app.app_context():
            user = User.create(
                username="testuser",
                email="test@example.com",
                password_hash="hash",
            )
            aspect = Aspect.create(
                name="Test",
                description="Desc",
                prompt="Prompt",
            )
            
            user_aspect = UserAspect.create(
                user_id=user.id,
                aspect_id=aspect.id,
            )
            
            # Initially should be None
            assert user_aspect.deleted_at is None
            
            # Mark as deleted
            user_aspect.deleted_at = datetime.now()
            user_aspect.save()
            
            # Refresh from DB
            user_aspect = UserAspect.get_by_id(user_aspect.id)
            assert user_aspect.deleted_at is not None
