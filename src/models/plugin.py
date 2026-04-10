"""Plugin models for paper reproducibility evaluation."""

import uuid
from datetime import datetime

from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField, TextField, UUIDField

from models.database import BaseModel, User


class Plugin(BaseModel):
    """Global plugin template (shared across all users).

    Represents a reproducibility evaluation criterion that can be applied
    to papers. Plugins are reusable templates with evaluation prompts.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=255)
    description = TextField()
    prompt = TextField()  # The evaluation prompt template
    is_default = BooleanField(default=False)  # Can't be deleted if True
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "plugins"
        indexes = (
            (("is_default",), False),  # Query default plugins
        )


class UserPlugin(BaseModel):
    """Per-user instance of a plugin.

    Represents a user's configuration of a plugin, including whether
    it's active and any custom prompt overrides.

    Constraint: unique(user_id, plugin_id) - One entry per user per plugin
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = ForeignKeyField(User, backref="user_plugins")
    plugin_id = ForeignKeyField(Plugin, backref="user_plugins")
    is_active = BooleanField(default=True)
    custom_prompt = TextField(null=True)  # Override default prompt
    deleted_at = DateTimeField(null=True)  # Soft delete
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "user_plugins"
        indexes = (
            (("user_id", "plugin_id"), True),  # Unique per user per plugin
            (("user_id", "is_active"), False),  # Query active plugins by user
        )
