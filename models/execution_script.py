"""Execution script models."""

from datetime import datetime
from peewee import CharField, TextField, ForeignKeyField, DateTimeField, IntegerField, UUIDField
from models.database import BaseModel, Job, User


class ExecutionScript(BaseModel):
    """User-provided or system script executed in container."""
    
    script_hash = CharField(primary_key=True, max_length=64)  # SHA256 hex
    script_text = TextField()                                  # Full script with shebang
    name = CharField(max_length=255)                          # User-friendly name
    description = TextField(null=True)                         # What the script checks/validates
    created_at = DateTimeField(default=datetime.now)
    created_by = ForeignKeyField(User, backref='execution_scripts', null=True)
    
    class Meta:
        table_name = 'execution_script'


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
