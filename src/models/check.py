"""Check models."""

from datetime import datetime

from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField, IntegerField, TextField, UUIDField

from models.database import BaseModel, Job, User


class Check(BaseModel):
    """System or user-provided check executed in container during analysis.

    Checks are identified by their SHA256 hash. This ensures:
    - Same check text always produces same hash
    - Check is stored once, referenced by hash
    - Can be versioned by having different hashes for different texts
    """

    script_hash = CharField(primary_key=True, max_length=64)  # SHA256 hex of script_text
    script_text = TextField()  # Full script with shebang
    name = CharField(max_length=255)  # User-friendly name
    description = TextField(null=True)  # What the check validates
    created_at = DateTimeField(default=datetime.now)
    created_by = ForeignKeyField(User, backref="checks", null=True)  # None = system check

    class Meta:
        table_name = "checks"


class UserCheck(BaseModel):
    """Per-user instance of a check.

    Tracks which checks each user has enabled for their analysis jobs.
    Similar to UserPlugin - allows users to select which checks run.

    One entry per user per check.
    """

    id = UUIDField(primary_key=True, default=lambda: __import__("uuid").uuid4())
    user_id = ForeignKeyField(User, backref="user_checks")
    script_hash = ForeignKeyField(Check, backref="user_instances")
    is_active = BooleanField(default=True)  # Whether check runs for this user
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "user_checks"
        indexes = (
            (("user_id", "script_hash"), True),  # Unique per user per check
            (("user_id", "is_active"), False),  # Query active checks by user
        )


class CheckResult(BaseModel):
    """Result of executing a check."""

    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job, backref="check_results")
    script_hash = CharField(max_length=64)  # Reference to Check
    exit_code = IntegerField()  # 0, 1, 2, or any exit code
    stdout = TextField(null=True)  # Check output
    stderr = TextField(null=True)  # Check errors
    duration_ms = IntegerField(default=0)  # Execution time
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "check_results"
