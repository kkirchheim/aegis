#!/usr/bin/env python3
"""
User Management CLI

Manage user activation status, list users, and delete users.

Usage:
    python manage_users.py list                    Show all users with status
    python manage_users.py activate <username>     Activate user account
    python manage_users.py deactivate <username>   Deactivate user account
    python manage_users.py delete <username>       Delete user account
    python manage_users.py reset-password <username> <password>  Reset user password
"""

import sys
import os
import hashlib
import secrets
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import models
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    from models.database import User, init_db
    from repositories import UserRepository
    USING_PEEWEE = True
except ImportError:
    USING_PEEWEE = False
    import sqlite3
    DATABASE = os.getenv("DATABASE", "reproducibility.db")


def hash_password(password):
    """Hash password using PBKDF2."""
    salt = secrets.token_hex(32)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwdhash.hex()}"


def ensure_column_exists():
    """Ensure is_active column exists in users table (legacy support)."""
    if USING_PEEWEE:
        # Peewee models handle this automatically
        init_db()
        return
    
    # Legacy raw SQL fallback
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 0")
        conn.commit()
        print("✓ Added is_active column to users table")
    except sqlite3.OperationalError:
        pass  # Column already exists
    finally:
        conn.close()


def list_users():
    """List all users with their status."""
    ensure_column_exists()
    
    if USING_PEEWEE:
        users = list(User.select().order_by(User.created_at.desc()))
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, username, email, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        users = c.fetchall()
        conn.close()
    
    if not users:
        print("No users found.")
        return
    
    # Prepare table data
    table_data = []
    for user in users:
        if USING_PEEWEE:
            status = "✓ Active" if user.is_active else "✗ Inactive"
            created = user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "N/A"
            username = user.username
            email = user.email
        else:
            status = "✓ Active" if user['is_active'] else "✗ Inactive"
            created = datetime.fromisoformat(user['created_at']).strftime("%Y-%m-%d %H:%M:%S")
            username = user['username']
            email = user['email']
        
        table_data.append([username, email, status, created])
    
    print("\n" + "="*80)
    print("USERS")
    print("="*80)
    
    if HAS_TABULATE:
        print(tabulate(
            table_data,
            headers=["Username", "Email", "Status", "Created"],
            tablefmt="grid"
        ))
    else:
        # Fallback to simple text formatting
        print(f"{'Username':<20} {'Email':<30} {'Status':<12} {'Created':<19}")
        print("-" * 80)
        for row in table_data:
            print(f"{row[0]:<20} {row[1]:<30} {row[2]:<12} {row[3]:<19}")
    
    print(f"\nTotal: {len(users)} user(s)\n")


def activate_user(username):
    """Activate a user account."""
    ensure_column_exists()
    
    if USING_PEEWEE:
        user = UserRepository.get_by_username(username)
        if not user:
            print(f"✗ User '{username}' not found")
            return False
        
        if user.is_active:
            print(f"ℹ User '{username}' is already active")
            return True
        
        # Activate user
        User.update(is_active=True).where(User.username == username).execute()
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id, is_active FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            print(f"✗ User '{username}' not found")
            conn.close()
            return False
        
        if user['is_active']:
            print(f"ℹ User '{username}' is already active")
            conn.close()
            return True
        
        # Activate user
        c.execute("UPDATE users SET is_active = 1 WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    
    print(f"✓ User '{username}' activated successfully")
    return True


def deactivate_user(username):
    """Deactivate a user account."""
    ensure_column_exists()
    
    if USING_PEEWEE:
        user = UserRepository.get_by_username(username)
        if not user:
            print(f"✗ User '{username}' not found")
            return False
        
        if not user.is_active:
            print(f"ℹ User '{username}' is already inactive")
            return True
        
        # Deactivate user
        User.update(is_active=False).where(User.username == username).execute()
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id, is_active FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            print(f"✗ User '{username}' not found")
            conn.close()
            return False
        
        if not user['is_active']:
            print(f"ℹ User '{username}' is already inactive")
            conn.close()
            return True
        
        # Deactivate user
        c.execute("UPDATE users SET is_active = 0 WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    
    print(f"✓ User '{username}' deactivated successfully")
    return True


def delete_user(username):
    """Delete a user account."""
    if USING_PEEWEE:
        user = UserRepository.get_by_username(username)
        if not user:
            print(f"✗ User '{username}' not found")
            return False
        
        # Confirm deletion
        response = input(f"Are you sure you want to delete user '{username}'? (yes/no): ").strip().lower()
        if response != 'yes':
            print("✗ Deletion cancelled")
            return False
        
        # Delete user
        User.delete_by_id(user.id)
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            print(f"✗ User '{username}' not found")
            conn.close()
            return False
        
        # Confirm deletion
        response = input(f"Are you sure you want to delete user '{username}'? (yes/no): ").strip().lower()
        if response != 'yes':
            print("✗ Deletion cancelled")
            conn.close()
            return False
        
        # Delete user
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    
    print(f"✓ User '{username}' deleted successfully")
    return True


def reset_password(username, password):
    """Reset a user's password."""
    if USING_PEEWEE:
        user = UserRepository.get_by_username(username)
        if not user:
            print(f"✗ User '{username}' not found")
            return False
        
        # Hash and update password
        password_hash = hash_password(password)
        User.update(password_hash=password_hash).where(User.username == username).execute()
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            print(f"✗ User '{username}' not found")
            conn.close()
            return False
        
        # Hash and update password
        password_hash = hash_password(password)
        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        conn.commit()
        conn.close()
    
    print(f"✓ Password reset for user '{username}' successfully")
    print(f"  New password: {password}")
    return True


def main():
    """Main CLI handler."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_users()
    elif command == "activate":
        if len(sys.argv) < 3:
            print("Error: Username required")
            print("Usage: python manage_users.py activate <username>")
            sys.exit(1)
        username = sys.argv[2]
        activate_user(username)
    elif command == "deactivate":
        if len(sys.argv) < 3:
            print("Error: Username required")
            print("Usage: python manage_users.py deactivate <username>")
            sys.exit(1)
        username = sys.argv[2]
        deactivate_user(username)
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Username required")
            print("Usage: python manage_users.py delete <username>")
            sys.exit(1)
        username = sys.argv[2]
        delete_user(username)
    elif command == "reset-password":
        if len(sys.argv) < 4:
            print("Error: Username and password required")
            print("Usage: python manage_users.py reset-password <username> <password>")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3]
        reset_password(username, password)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
