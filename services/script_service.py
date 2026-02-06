"""Service for managing user scripts and activations."""

import json
from typing import List, Dict, Any, Optional
from models.execution_script import ExecutionScript, UserScript
from models.database import User
import uuid


class ScriptService:
    """Service for user script management."""
    
    @staticmethod
    def get_all_available_scripts(user_id: int) -> List[Dict[str, Any]]:
        """Get all available scripts for a user (default + their own).
        
        Returns:
            List of script dicts with {script_hash, name, description, created_by, is_active, created_at}
        """
        scripts = []
        
        # Get all scripts (default + user's own)
        for script in ExecutionScript.select():
            is_owned = script.created_by_id == user_id if script.created_by_id else False
            is_default = script.created_by_id is None
            
            # Check if user has activated this script
            try:
                user_script = UserScript.get(
                    UserScript.user_id == user_id,
                    UserScript.script_hash == script.script_hash
                )
                is_active = user_script.is_active
            except:
                # Default scripts are inactive by default; user scripts are active
                is_active = is_owned  # Active if user created it, inactive if default
            
            scripts.append({
                'script_hash': script.script_hash,
                'name': script.name,
                'description': script.description or '',
                'script_text_preview': script.script_text[:200] if len(script.script_text) > 200 else script.script_text,
                'created_by': script.created_by.username if script.created_by else 'System',
                'is_active': is_active,
                'is_default': is_default,
                'is_owned': is_owned,
                'created_at': script.created_at.isoformat() if hasattr(script.created_at, 'isoformat') else str(script.created_at)
            })
        
        return scripts
    
    @staticmethod
    def get_active_scripts_for_user(user_id: int) -> List[Dict[str, Any]]:
        """Get only active scripts for a user (to run in analysis).
        
        Returns:
            List of {script_hash, name, description, script_text}
        """
        active_scripts = []
        
        for user_script in (UserScript
                            .select()
                            .where(UserScript.user_id == user_id, UserScript.is_active == True)):
            try:
                script = ExecutionScript.get_by_id(user_script.script_hash)
                active_scripts.append({
                    'script_hash': script.script_hash,
                    'name': script.name,
                    'description': script.description or '',
                    'script_text': script.script_text
                })
            except:
                pass  # Skip if script not found
        
        return active_scripts
    
    @staticmethod
    def activate_script(user_id: int, script_hash: str) -> bool:
        """Activate a script for a user.
        
        Creates UserScript entry if not exists, sets is_active=True.
        
        Args:
            user_id: User ID
            script_hash: Script hash
            
        Returns:
            True if activated, False if script not found
        """
        # Verify script exists
        try:
            script = ExecutionScript.get_by_id(script_hash)
        except:
            return False
        
        # Create or update UserScript
        user_script, created = UserScript.get_or_create(
            user_id=user_id,
            script_hash=script_hash,
            defaults={'is_active': True}
        )
        
        if not created and not user_script.is_active:
            user_script.is_active = True
            user_script.save()
        
        return True
    
    @staticmethod
    def deactivate_script(user_id: int, script_hash: str) -> bool:
        """Deactivate a script for a user.
        
        Args:
            user_id: User ID
            script_hash: Script hash
            
        Returns:
            True if deactivated, False if not found
        """
        try:
            user_script = UserScript.get(
                UserScript.user_id == user_id,
                UserScript.script_hash == script_hash
            )
            user_script.is_active = False
            user_script.save()
            return True
        except:
            return False
    
    @staticmethod
    def create_user_script(user_id: int, name: str, script_text: str, 
                          description: str = None) -> Optional[Dict[str, Any]]:
        """Create a new user script.
        
        Args:
            user_id: User creating the script
            name: Script name
            script_text: Full script text (with shebang)
            description: Optional description
            
        Returns:
            Script dict on success, None on failure
        """
        from utils.script_utils import hash_script, get_or_create_script
        
        try:
            script = get_or_create_script(name, script_text, user_id=user_id, description=description)
            
            # Activate for this user
            ScriptService.activate_script(user_id, script.script_hash)
            
            return {
                'script_hash': script.script_hash,
                'name': script.name,
                'description': script.description,
                'created_by': 'You',
                'is_active': True,
                'created_at': script.created_at.isoformat() if hasattr(script.created_at, 'isoformat') else str(script.created_at)
            }
        except Exception as e:
            print(f"Failed to create script: {e}")
            return None
    
    @staticmethod
    def update_script_description(script_hash: str, description: str) -> bool:
        """Update a script's description.
        
        Args:
            script_hash: Script hash
            description: New description
            
        Returns:
            True if updated, False if not found
        """
        try:
            script = ExecutionScript.get_by_id(script_hash)
            script.description = description
            script.save()
            return True
        except:
            return False
    
    @staticmethod
    def delete_user_script(user_id: int, script_hash: str) -> bool:
        """Delete a user's script (only if user created it).
        
        Args:
            user_id: User ID (must be creator)
            script_hash: Script hash
            
        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            # Only allow deletion if user created the script
            script = ExecutionScript.get_by_id(script_hash)
            if script.created_by_id != user_id:
                return False
            
            # Delete the script and all user references
            UserScript.delete().where(UserScript.script_hash == script_hash).execute()
            script.delete_instance()
            return True
        except:
            return False
