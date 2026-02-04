# User Activation - Quick Start Guide

## TL;DR

New users register → accounts are **INACTIVE** → admin must activate them → users can login.

## Admin Commands

```bash
# See all users
python3 manage_users.py list

# Activate a user
python3 manage_users.py activate <username>

# Deactivate a user
python3 manage_users.py deactivate <username>

# Delete a user
python3 manage_users.py delete <username>
```

## User Flow

```
User Registration
        ↓
"Account created. Awaiting activation by admin."
        ↓
Try to login → Error: "Account not activated yet"
        ↓
Admin runs: manage_users.py activate <username>
        ↓
User logs in successfully
```

## Example Session

```bash
# 1. Check pending users
$ python3 manage_users.py list
Username             Email                          Status       Created            
john_doe             john@example.com               ✗ Inactive   2026-02-04 12:00:00
jane_smith           jane@example.com               ✓ Active     2026-02-04 11:30:00

# 2. Activate john_doe
$ python3 manage_users.py activate john_doe
✓ User 'john_doe' activated successfully

# 3. Verify activation
$ python3 manage_users.py list
Username             Email                          Status       Created            
john_doe             john@example.com               ✓ Active     2026-02-04 12:00:00
jane_smith           jane@example.com               ✓ Active     2026-02-04 11:30:00
```

## HTTP Response Codes

| Scenario | Code | Message |
|----------|------|---------|
| Register | 201 | "Account created. Awaiting activation by admin." |
| Login - Wrong password | 401 | "Invalid username or password" |
| Login - Inactive user | 403 | "Account not activated yet" |
| Login - Success | 200 | "Login successful" |

## Database Column

```sql
-- Added to users table
is_active BOOLEAN DEFAULT 0

-- 0 = Inactive (cannot login)
-- 1 = Active (can login)
```

## What Changed in Code

### Registration (`/register`)
- ✗ Users NO LONGER logged in immediately
- ✓ Users created with `is_active = 0`
- ✓ Shown message about awaiting activation

### Login (`/login`)
- ✓ Added check: `if not user['is_active']: return 403`
- ✓ Returns "Account not activated yet" for inactive users

### Database
- ✓ New column: `is_active BOOLEAN DEFAULT 0`
- ✓ Auto-migration for existing databases

## Files Changed

```
app.py              - Database schema + login/register logic
requirements.txt    - Added tabulate (optional)
manage_users.py     - NEW: Admin CLI tool
USER_ACTIVATION.md  - Detailed documentation
tests/test_user_activation.py - NEW: Test suite (all passing ✓)
```

## Deployment

1. **No special steps needed** - Schema auto-migrates
2. **Existing users:** Will be inactive after migration
3. **Activate as needed:** `python3 manage_users.py activate <username>`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Database is read-only | `chown user:user reproducibility.db` |
| User can't login | Run `python3 manage_users.py list` and check status |
| "No users found" | Database migration not run (run app once to migrate) |

## Security Notes

✓ Users cannot access app without activation  
✓ Activation is admin-controlled (CLI only)  
✓ No remote activation API  
✓ Default is inactive (safer than active)  

---

For detailed documentation, see: [USER_ACTIVATION.md](USER_ACTIVATION.md)
