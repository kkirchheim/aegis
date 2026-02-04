# User Activation System

This document describes the user activation system implementation for the Paper Reproducibility Checker.

## Overview

The user activation system enforces admin approval for new user registrations. When users register, they create accounts with `is_active = False` status. Only admins can activate users via the CLI, allowing them to login.

## Features

✓ New users register as **inactive** by default  
✓ Inactive users **cannot login** (receive 403 error)  
✓ Admins can activate/deactivate users via CLI  
✓ Admins can view all users and their status  
✓ Admins can delete user accounts  

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 0,      -- NEW: User activation status
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

The `is_active` column:
- **Type:** BOOLEAN (stored as 0=False, 1=True in SQLite)
- **Default:** 0 (False) - new users are inactive
- **Migration:** Automatically added to existing databases via ALTER TABLE in `init_db()`

## API Changes

### Registration Endpoint: `POST /register`

**Before:**
- Users were logged in immediately after registration
- Users could access the app right away

**After:**
- Users are created with `is_active = False`
- Response: 201 Created with message "Account created. Awaiting activation by admin."
- Users are NOT logged in
- Users receive 401 when attempting to login until activated

### Login Endpoint: `POST /login`

**Before:**
- Only checked username/password

**After:**
- Checks username/password first
- Then checks `is_active` status
- If inactive: Returns 403 Forbidden with message "Account not activated yet"
- If active: Returns 200 OK and logs user in

**HTTP Status Codes:**
- 200 OK - Login successful (active user, correct password)
- 401 Unauthorized - Invalid username/password
- 403 Forbidden - Correct password but user is inactive

## CLI Tool: `manage_users.py`

Standalone command-line tool for user management. No Flask dependencies required.

### Installation

```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
python3 manage_users.py --help
```

### Commands

#### 1. List All Users

```bash
python3 manage_users.py list
```

Output:
```
================================================================================
USERS
================================================================================
Username             Email                          Status       Created            
--------------------------------------------------------------------------------
john_doe             john@example.com               ✓ Active     2026-02-04 12:00:00
jane_smith           jane@example.com               ✗ Inactive   2026-02-04 12:15:30

Total: 2 user(s)
```

#### 2. Activate User

```bash
python3 manage_users.py activate <username>
```

Example:
```bash
python3 manage_users.py activate jane_smith
# Output: ✓ User 'jane_smith' activated successfully
```

#### 3. Deactivate User

```bash
python3 manage_users.py deactivate <username>
```

Example:
```bash
python3 manage_users.py deactivate john_doe
# Output: ✓ User 'john_doe' deactivated successfully
```

#### 4. Delete User

```bash
python3 manage_users.py delete <username>
```

Example:
```bash
python3 manage_users.py delete jane_smith
# Output: Are you sure you want to delete user 'jane_smith'? (yes/no): yes
#         ✓ User 'jane_smith' deleted successfully
```

### Database Configuration

The tool uses `reproducibility.db` by default, but you can override it:

```bash
DATABASE=/custom/path/db.db python3 manage_users.py list
```

## Code Changes Summary

### 1. `app.py` - Database Initialization

**File:** `app.py` (lines ~118-135)

Added `is_active` column to users table:
```python
c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        ...
        is_active BOOLEAN DEFAULT 0,
        ...
    )
""")

# Migration for existing databases
try:
    c.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 0")
    app.logger.info("Added is_active column to users table")
except:
    pass  # Column already exists
```

### 2. `app.py` - Registration Handler

**File:** `app.py` (lines ~1110-1125)

Changed to create inactive users:
```python
# Create user (inactive by default)
password_hash = hash_password(password)
c.execute(
    "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 0)",
    (username, email, password_hash)
)

return jsonify({
    "message": "Account created. Awaiting activation by admin.",
    "redirect": "/login"
}), 201
```

### 3. `app.py` - Login Handler

**File:** `app.py` (lines ~1154-1175)

Added activation check:
```python
c.execute("SELECT id, password_hash, username, is_active FROM users WHERE username = ?", 
          (username,))
user = c.fetchone()

if not user or not verify_password(password, user[1]):
    return jsonify({"error": "Invalid username or password"}), 401

# Check if user is active
if not user[3]:  # is_active is the 4th column (index 3)
    return jsonify({"error": "Account not activated yet"}), 403

# Log them in
session['user_id'] = user[0]
session['username'] = user[2]

return jsonify({"message": "Login successful", "redirect": "/"}), 200
```

## User Journey

### Admin Workflow

1. **Create User (Auto)**
   - User navigates to `/register`
   - Enters username, email, password
   - Account created with `is_active = False`
   - Redirected to login page with message

2. **Review & Activate**
   - Admin runs: `python3 manage_users.py list`
   - Identifies pending users (status: ✗ Inactive)
   - Admin runs: `python3 manage_users.py activate <username>`

3. **User Can Now Login**
   - User logs in with credentials
   - System checks: password ✓, is_active ✓
   - Login successful, redirected to home page

### User Workflow

1. **Register**
   ```
   Register form → Submit → Account created message
   ```

2. **Await Activation**
   ```
   Try to login → Error: "Account not activated yet"
   ```

3. **Activation by Admin**
   ```
   [Admin runs: manage_users.py activate <username>]
   ```

4. **Login & Use App**
   ```
   Login form → Submit → Redirected to home page
   ```

## Error Messages

| Scenario | HTTP Status | Message |
|----------|------------|---------|
| Register successful | 201 Created | "Account created. Awaiting activation by admin." |
| Login with wrong password | 401 Unauthorized | "Invalid username or password" |
| Login with inactive account | 403 Forbidden | "Account not activated yet" |
| Login with active account | 200 OK | "Login successful" |
| Activate non-existent user | N/A | "User '<name>' not found" |
| Activate already-active user | N/A | "User '<name>' is already active" |

## Testing

Comprehensive test suite included in `tests/test_user_activation.py`

### Run Tests

```bash
python3 tests/test_user_activation.py
```

Tests cover:
- ✓ New users register as inactive
- ✓ Password verification works correctly
- ✓ Inactive users cannot login
- ✓ Active users can login
- ✓ User activation changes status
- ✓ Full login flow (register → inactive → activate → login)

## Security Considerations

1. **Default Inactive State**
   - Users cannot access the system until explicitly approved
   - Prevents unauthorized access

2. **Password Storage**
   - Passwords hashed with PBKDF2-SHA256
   - Not affected by activation system

3. **Session Management**
   - Active user check only happens at login
   - Active/Inactive status changes take effect on next login

4. **CLI Tool**
   - Requires direct database access
   - Should only be run by admin with filesystem access
   - No remote API exposure

## Migration Guide

### For Existing Deployments

The system includes automatic migration:

1. **Database:** The `is_active` column is automatically added to existing users tables with `ALTER TABLE`
2. **Existing Users:** Automatically set to `is_active = 0` (inactive)
3. **Activation:** Admin must manually activate existing users via CLI

#### Steps:

```bash
# 1. Update code (already done)
git pull

# 2. Restart Flask app
# App will auto-migrate on startup

# 3. Review existing users
python3 manage_users.py list

# 4. Activate approved users
python3 manage_users.py activate <username>

# 5. Verify status
python3 manage_users.py list
```

## Dependencies

### New Dependencies

- `tabulate>=0.9.0` - For pretty table output in CLI (optional fallback to plain text)

### Existing Dependencies (No Changes)

- Flask, sqlite3, hashlib, secrets (all standard/existing)

## Troubleshooting

### "Attempt to write a readonly database"

The database file is owned by a different user. Fix permissions:

```bash
chmod 644 reproducibility.db
chown $USER:$USER reproducibility.db
```

### CLI shows "No users found" after registration

Database migration may not have run. The app creates the `is_active` column automatically on startup.

### User can't login after activation

1. Verify activation: `python3 manage_users.py list`
2. Check that status shows ✓ Active
3. Try logging in again (session may be cached)
4. Clear browser cookies if needed

## Future Enhancements

Potential improvements (out of scope for current implementation):

- [ ] Web UI for user management (admin dashboard)
- [ ] Email notifications on account activation
- [ ] Admin dashboard to manage users without CLI
- [ ] Automatic activation based on email domain whitelist
- [ ] Audit log of activation/deactivation events
- [ ] User roles (admin, reviewer, viewer)
- [ ] Bulk user import from CSV
