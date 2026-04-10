"""Execution script models."""

from datetime import datetime
from peewee import CharField, TextField, ForeignKeyField, DateTimeField, IntegerField, UUIDField, BooleanField
from models.database import BaseModel, Job, User


class ExecutionScript(BaseModel):
    """System or user-provided script executed in container during analysis.
    
    Scripts are identified by their SHA256 hash. This ensures:
    - Same script text always produces same hash
    - Script is stored once, referenced by hash
    - Can be versioned by having different hashes for different texts
    """
    
    script_hash = CharField(primary_key=True, max_length=64)  # SHA256 hex of script_text
    script_text = TextField()                                  # Full script with shebang
    name = CharField(max_length=255)                          # User-friendly name
    description = TextField(null=True)                         # What the script checks/validates
    created_at = DateTimeField(default=datetime.now)
    created_by = ForeignKeyField(User, backref='execution_scripts', null=True)  # None = system script
    
    class Meta:
        table_name = 'execution_script'


class UserScript(BaseModel):
    """Per-user instance of an execution script.
    
    Tracks which scripts each user has enabled for their analysis jobs.
    Similar to UserAspect - allows users to select which scripts run.
    
    One entry per user per script.
    """
    id = UUIDField(primary_key=True, default=lambda: __import__('uuid').uuid4())
    user_id = ForeignKeyField(User, backref='user_scripts')
    script_hash = ForeignKeyField(ExecutionScript, backref='user_instances')
    is_active = BooleanField(default=True)  # Whether script runs for this user
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'user_script'
        indexes = (
            (('user_id', 'script_hash'), True),  # Unique per user per script
            (('user_id', 'is_active'), False),   # Query active scripts by user
        )


class ExecutionScriptResult(BaseModel):
    """Result of executing a script."""
    
    id = UUIDField(primary_key=True)
    job = ForeignKeyField(Job, backref='script_results')
    script_hash = CharField(max_length=64)  # Reference to ExecutionScript
    exit_code = IntegerField()              # 0, 1, 2, or any exit code
    stdout = TextField(null=True)           # Script output
    stderr = TextField(null=True)           # Script errors
    duration_ms = IntegerField(default=0)   # Execution time
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'execution_script_result'
