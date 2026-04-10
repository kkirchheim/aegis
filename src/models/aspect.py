"""Aspect plugin models for paper reproducibility evaluation."""

import uuid
from datetime import datetime

from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField, TextField, UUIDField

from models.database import BaseModel, User


class Aspect(BaseModel):
    """Global aspect template (shared across all users).

    Represents a reproducibility evaluation criterion that can be applied
    to papers. Aspects are reusable templates with evaluation prompts.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=255)
    description = TextField()
    prompt = TextField()  # The evaluation prompt template
    is_default = BooleanField(default=False)  # Can't be deleted if True
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "aspects"
        indexes = (
            (("is_default",), False),  # Query default aspects
        )


class UserAspect(BaseModel):
    """Per-user instance of an aspect.

    Represents a user's configuration of an aspect, including whether
    it's active and any custom prompt overrides.

    Constraint: unique(user_id, aspect_id) - One entry per user per aspect
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = ForeignKeyField(User, backref="user_aspects")
    aspect_id = ForeignKeyField(Aspect, backref="user_aspects")
    is_active = BooleanField(default=True)
    custom_prompt = TextField(null=True)  # Override default prompt
    deleted_at = DateTimeField(null=True)  # Soft delete
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "user_aspects"
        indexes = (
            (("user_id", "aspect_id"), True),  # Unique per user per aspect
            (("user_id", "is_active"), False),  # Query active aspects by user
        )
