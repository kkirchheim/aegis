# Admin Features Documentation

This document describes the admin features for account management in the Paper Reproducibility Checker.

## Features Implemented

### 1. Default Admin User
- **Automatic Creation**: A default admin user is created automatically on app startup (if it doesn't exist)
- **Default Credentials**:
  - Username: `admin`
  - Password: `admin`
  - Email: `admin@example.com`
- **Status**: Always active and cannot be deactivated
- **Important**: The admin password should be changed on first login using the "Change Password" feature

### 2. Admin Panel (`/admin`)
**Access**: Only accessible to users logged in as admin

The admin panel allows administrators to manage all user accounts in the system.

#### Features:
- **View All Users**: Table listing all registered users with the following columns:
  - Username (with admin badge for admin user)
  - Email address
  - Status (Active/Inactive badge)
  - Creation date
  - Action buttons

#### User Management Actions:
- **Activate User**: Button appears for inactive users
  - Reactivates an inactive account
  - Only non-admin users can be activated
  
- **Deactivate User**: Button appears for active users
  - Marks a user as inactive (they cannot log in)
  - Cannot be performed on the admin account
  
- **Delete User**: Red button with confirmation dialog
  - Permanently deletes a user account
  - Also deletes all of the user's analysis jobs and PDF files
  - Cannot be performed on the admin account
  - Shows confirmation dialog with warning about cascading deletions

### 3. Admin API Endpoints

All admin endpoints require admin authentication (`@require_admin` decorator).

#### GET `/admin`
- Serves the admin panel HTML page
- Redirects to login if not authenticated
- Returns 403 if user is not admin

#### GET `/api/admin/users`
- Returns JSON list of all users with full details
- Response format:
```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_active": true,
    "created_at": "2026-02-04 13:20:00"
  },
  {
    "id": 2,
    "username": "john",
    "email": "john@example.com",
    "is_active": true,
    "created_at": "2026-02-04 14:00:00"
  }
]
```

#### POST `/api/admin/users/<user_id>/activate`
- Activates an inactive user
- Parameters: `user_id` (integer) in URL path
- Returns: `{"ok": true, "message": "User ... activated"}`
- Error cases:
  - 404: User not found
  - 403: Not admin

#### POST `/api/admin/users/<user_id>/deactivate`
- Deactivates an active user
- Parameters: `user_id` (integer) in URL path
- Returns: `{"ok": true, "message": "User ... deactivated"}`
- Error cases:
  - 404: User not found
  - 400: Cannot deactivate admin user
  - 403: Not admin

#### POST `/api/admin/users/<user_id>/delete`
- Permanently deletes a user and all their jobs
- Parameters: `user_id` (integer) in URL path
- Returns: `{"ok": true, "message": "User ... deleted"}`
- Error cases:
  - 404: User not found
  - 400: Cannot delete admin user
  - 403: Not admin
- Side effects:
  - Deletes all jobs owned by the user
  - Deletes all PDF files associated with those jobs
  - Deletes all job-related data (events, artifacts, analyses, etc.)

### 4. Admin Decorator (`@require_admin`)
New decorator for protecting admin-only routes:
```python
@require_admin
def admin_route():
    # Only accessible to admin user
    pass
```

Checks:
1. User must be logged in (`user_id` in session)
2. Username must be exactly `"admin"`
3. Returns 401 if not logged in
4. Returns 403 if logged in but not admin

### 5. Password Change Feature (`/change-password`)
**Access**: Available to all logged-in users (admin and regular users)

#### Features:
- Dedicated password change page
- Form fields:
  - Current Password (required)
  - New Password (required, minimum 8 characters)
  - Confirm New Password (must match new password)
  
#### User Experience:
- Form validation on client side
- Server-side validation
- Error messages for:
  - Missing fields
  - Password too short
  - Passwords don't match
  - Incorrect current password
- Success message with auto-redirect to home after 2 seconds

#### API Endpoint: POST `/api/change-password`
- Requires authentication
- Request body:
```json
{
  "old_password": "currentpass123",
  "new_password": "newpass456789",
  "confirm_password": "newpass456789"
}
```
- Response on success:
```json
{
  "ok": true,
  "message": "Password changed successfully"
}
```
- Error responses:
  - 400: Missing fields, password too short, passwords don't match, wrong old password
  - 404: User not found (edge case)
  - 500: Server error

#### Password Security:
- Uses PBKDF2-SHA256 hashing with salt
- 100,000 iterations (industry standard)
- New password is hashed and stored in database
- Old password is verified before allowing change

### 6. UI Integration

#### Navbar Updates
The navbar now includes:
- **Admin Panel Link**: Shows "👥 Admin Panel" for admin users only
- **Change Password Link**: Shows "🔑 Change Password" for all logged-in users

These are in the user dropdown menu in the navbar.

## Usage Scenarios

### Scenario 1: First Login
1. Admin user logs in with default credentials (admin/admin)
2. Goes to navbar → user menu → "🔑 Change Password"
3. Changes password from "admin" to something secure
4. Can then access admin panel via navbar → user menu → "👥 Admin Panel"

### Scenario 2: Activate New User
1. New user registers (account is inactive by default)
2. Admin goes to `/admin` and sees new user
3. Clicks "Activate" button next to user
4. User can now log in

### Scenario 3: Remove Inactive User
1. Admin goes to `/admin`
2. Sees inactive user
3. Clicks red "Delete" button
4. Confirms deletion in modal
5. User account and all their jobs are deleted

### Scenario 4: Manage User Access
1. Admin can deactivate a user temporarily
   - User cannot log in until reactivated
   - User's data is preserved
2. Admin can permanently delete a user
   - User account and all their jobs are removed
   - Cannot be undone

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

Key columns:
- `username`: Unique username (check for `username == 'admin'`)
- `email`: Email address
- `password_hash`: Hashed password (PBKDF2-SHA256 format: `salt$hash`)
- `is_active`: Boolean flag for user activation
- `created_at`: Account creation timestamp

## Security Considerations

1. **Admin User Protection**:
   - Admin user cannot be deactivated or deleted
   - Only the `admin` username has admin privileges
   - Check enforced at both decorator and endpoint level

2. **Password Security**:
   - Passwords are hashed with PBKDF2-SHA256 + salt
   - Password change validates old password first
   - Minimum 8 characters enforced

3. **API Protection**:
   - All admin endpoints require `@require_admin` decorator
   - User must be logged in AND have username "admin"
   - Regular users get 403 error if they try to access admin endpoints

4. **Data Integrity**:
   - Cascading delete when user is deleted (jobs and related data)
   - Unique constraints on username and email

## Testing

A comprehensive test suite is provided in `test_admin_features.py`:

```bash
python3 test_admin_features.py
```

Tests cover:
1. Admin user creation on startup
2. Password verification
3. Password change functionality
4. User activation/deactivation
5. User deletion
6. Admin protection (cannot delete/deactivate)
7. User listing

All tests pass ✓

## Files Modified/Created

### Modified Files:
- `app.py`: Added admin decorator, endpoints, and user creation
- `templates/navbar.html`: Added admin panel and change password links

### New Files:
- `templates/admin.html`: Admin panel UI
- `templates/change-password.html`: Password change UI
- `test_admin_features.py`: Admin features test suite
- `ADMIN_FEATURES.md`: This documentation file

## Future Enhancements

Possible improvements:
1. Role-based access control (multiple admin levels)
2. Audit logging for admin actions
3. Admin user creation with custom email
4. Bulk user operations (activate/deactivate multiple users)
5. User search and filtering
6. Quota management per user
7. Admin dashboard with statistics
