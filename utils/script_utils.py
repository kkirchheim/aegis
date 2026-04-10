"""Utilities for execution scripts."""

import hashlib
from models.execution_script import ExecutionScript


def hash_script(script_text: str) -> str:
    """Generate stable hash for script text."""
    return hashlib.sha256(script_text.encode()).hexdigest()


def get_or_create_script(name: str, script_text: str, user_id=None, description=None):
    """Get existing script or create new one.
    
    Args:
        name: Human-friendly name
        script_text: Full script text with shebang
        user_id: User creating the script (None for system scripts)
        description: What the script checks or validates
    
    Returns:
        ExecutionScript instance
    """
    script_hash = hash_script(script_text)
    
    try:
        script = ExecutionScript.get_by_id(script_hash)
        # Update description if provided and different
        if description and script.description != description:
            script.description = description
            script.save()
        return script
    except:
        # Create new script
        script = ExecutionScript.create(
            script_hash=script_hash,
            script_text=script_text,
            name=name,
            description=description,
            created_by=user_id
        )
        return script


# Default system scripts (Phase 1 MVP)
DEFAULT_SCRIPTS = {
    "README Exists": {
        "text": """#!/bin/bash
test -f README.md && exit 0 || exit 1
""",
        "description": "Verifies that a README.md file exists in the repository root"
    }
}


def seed_default_scripts():
    """Create default system scripts on app startup.
    
    This is idempotent - calling multiple times is safe.
    """
    for name, config in DEFAULT_SCRIPTS.items():
        try:
            script_text = config.get("text") if isinstance(config, dict) else config
            description = config.get("description") if isinstance(config, dict) else None
            get_or_create_script(name, script_text, user_id=None, description=description)
        except Exception as e:
            print(f"Warning: Failed to seed script '{name}': {e}")
