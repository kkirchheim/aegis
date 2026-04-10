"""Utilities for execution checks."""

import hashlib
from models.check import Check


def hash_script(script_text: str) -> str:
    """Generate stable hash for script text."""
    return hashlib.sha256(script_text.encode()).hexdigest()


def get_or_create_check(name: str, script_text: str, user_id=None, description=None):
    """Get existing check or create new one.

    Args:
        name: Human-friendly name
        script_text: Full script text with shebang
        user_id: User creating the check (None for system checks)
        description: What the check validates

    Returns:
        Check instance
    """
    script_hash = hash_script(script_text)

    try:
        check = Check.get_by_id(script_hash)
        # Update description if provided and different
        if description and check.description != description:
            check.description = description
            check.save()
        return check
    except:
        # Create new check
        check = Check.create(
            script_hash=script_hash,
            script_text=script_text,
            name=name,
            description=description,
            created_by=user_id
        )
        return check


# Default system checks (Phase 1 MVP)
DEFAULT_CHECKS = {
    "README Exists": {
        "text": """#!/bin/bash
test -f README.md && exit 0 || exit 1
""",
        "description": "Verifies that a README.md file exists in the repository root"
    }
}


def seed_default_checks():
    """Create default system checks on app startup.

    This is idempotent - calling multiple times is safe.
    """
    for name, config in DEFAULT_CHECKS.items():
        try:
            script_text = config.get("text") if isinstance(config, dict) else config
            description = config.get("description") if isinstance(config, dict) else None
            get_or_create_check(name, script_text, user_id=None, description=description)
        except Exception as e:
            print(f"Warning: Failed to seed check '{name}': {e}")
