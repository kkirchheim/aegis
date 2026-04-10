"""Service for managing user checks and activations."""

import json
from typing import List, Dict, Any, Optional
from models.check import Check, UserCheck
from models.database import User
import uuid


class CheckService:
    """Service for user check management."""

    @staticmethod
    def get_all_available_checks(user_id: int) -> List[Dict[str, Any]]:
        """Get all available checks for a user (default + their own).

        Returns:
            List of check dicts with {script_hash, name, description, created_by, is_active, created_at}
        """
        checks = []

        # Get all checks (default + user's own)
        for check in Check.select():
            is_owned = check.created_by_id == user_id if check.created_by_id else False
            is_default = check.created_by_id is None

            # Check if user has activated this check
            try:
                user_check = UserCheck.get(
                    UserCheck.user_id == user_id,
                    UserCheck.script_hash == check.script_hash
                )
                is_active = user_check.is_active
            except:
                # Default checks are inactive by default; user checks are active
                is_active = is_owned  # Active if user created it, inactive if default

            checks.append({
                'script_hash': check.script_hash,
                'name': check.name,
                'description': check.description or '',
                'script_text_preview': check.script_text[:200] if len(check.script_text) > 200 else check.script_text,
                'created_by': check.created_by.username if check.created_by else 'System',
                'is_active': is_active,
                'is_default': is_default,
                'is_owned': is_owned,
                'created_at': check.created_at.isoformat() if hasattr(check.created_at, 'isoformat') else str(check.created_at)
            })

        return checks

    @staticmethod
    def get_active_checks_for_user(user_id: int) -> List[Dict[str, Any]]:
        """Get only active checks for a user (to run in analysis).

        Returns:
            List of {script_hash, name, description, script_text}
        """
        active_checks = []

        for user_check in (UserCheck
                            .select()
                            .where(UserCheck.user_id == user_id, UserCheck.is_active == True)):
            try:
                check = Check.get_by_id(user_check.script_hash)
                active_checks.append({
                    'script_hash': check.script_hash,
                    'name': check.name,
                    'description': check.description or '',
                    'script_text': check.script_text
                })
            except:
                pass  # Skip if check not found

        return active_checks

    @staticmethod
    def activate_check(user_id: int, script_hash: str) -> bool:
        """Activate a check for a user.

        Creates UserCheck entry if not exists, sets is_active=True.
        """
        # Verify check exists
        try:
            check = Check.get_by_id(script_hash)
        except:
            return False

        # Create or update UserCheck
        user_check, created = UserCheck.get_or_create(
            user_id=user_id,
            script_hash=script_hash,
            defaults={'is_active': True}
        )

        if not created and not user_check.is_active:
            user_check.is_active = True
            user_check.save()

        return True

    @staticmethod
    def deactivate_check(user_id: int, script_hash: str) -> bool:
        """Deactivate a check for a user."""
        try:
            user_check = UserCheck.get(
                UserCheck.user_id == user_id,
                UserCheck.script_hash == script_hash
            )
            user_check.is_active = False
            user_check.save()
            return True
        except:
            return False

    @staticmethod
    def create_user_check(user_id: int, name: str, script_text: str,
                          description: str = None) -> Optional[Dict[str, Any]]:
        """Create a new user check."""
        from utils.check_utils import hash_script, get_or_create_check

        try:
            check = get_or_create_check(name, script_text, user_id=user_id, description=description)

            # Activate for this user
            CheckService.activate_check(user_id, check.script_hash)

            return {
                'script_hash': check.script_hash,
                'name': check.name,
                'description': check.description,
                'created_by': 'You',
                'is_active': True,
                'created_at': check.created_at.isoformat() if hasattr(check.created_at, 'isoformat') else str(check.created_at)
            }
        except Exception as e:
            print(f"Failed to create check: {e}")
            return None

    @staticmethod
    def update_check_description(script_hash: str, description: str) -> bool:
        """Update a check's description."""
        try:
            check = Check.get_by_id(script_hash)
            check.description = description
            check.save()
            return True
        except:
            return False

    @staticmethod
    def delete_user_check(user_id: int, script_hash: str) -> bool:
        """Delete a user's check (only if user created it)."""
        try:
            # Only allow deletion if user created the check
            check = Check.get_by_id(script_hash)
            if check.created_by_id != user_id:
                return False

            # Delete the check and all user references
            UserCheck.delete().where(UserCheck.script_hash == script_hash).execute()
            check.delete_instance()
            return True
        except:
            return False
