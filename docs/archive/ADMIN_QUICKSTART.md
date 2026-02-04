# Admin Features - Quick Start Guide

## First Time Setup

### Step 1: Start the Application
```bash
python3 app.py
```

You should see:
```
✓ Admin user created (username: admin, password: admin)
⚠️  Please change the admin password on first login!
```

### Step 2: Log In as Admin
1. Open browser to `http://localhost:5000`
2. Click "Login" 
3. Username: `admin`
4. Password: `admin`
5. Click "Login"

### Step 3: Change Default Password (IMPORTANT!)
1. Click user avatar (👤) in top-right
2. Select "🔑 Change Password"
3. Enter:
   - Current Password: `admin`
   - New Password: `yourSecurePassword123`
   - Confirm Password: `yourSecurePassword123`
4. Click "Change Password"
5. You'll be redirected to home

### Step 4: Access Admin Panel
1. Click user avatar (👤) in top-right
2. Select "👥 Admin Panel"
3. You should see a table of all users

## Managing Users

### Activate a User
1. Go to Admin Panel (`/admin`)
2. Find inactive user (red "✗ Inactive" badge)
3. Click "Activate" button
4. User can now log in

### Deactivate a User
1. Go to Admin Panel
2. Find active user
3. Click "Deactivate" button
4. User cannot log in anymore
5. User's data is preserved (can be reactivated later)

### Delete a User
1. Go to Admin Panel
2. Find user to delete
3. Click red "Delete" button
4. Confirm in popup dialog
5. User and ALL their analysis jobs are permanently deleted

## Changing Your Password

As any user (including admin):
1. Click user avatar (👤) in top-right
2. Select "🔑 Change Password"
3. Enter current and new passwords
4. Click "Change Password"

## Common Tasks

### Task: User registration pending activation
**Scenario**: User registers but account shows as inactive

**Solution**:
1. Go to Admin Panel
2. Find the user (red "✗ Inactive" badge)
3. Click "Activate"
4. User can now log in

### Task: User cannot log in anymore
**Scenario**: User forgot password or account locked

**Solutions**:
- **If password forgotten**: User needs to re-register (current system)
- **If account deactivated**: Admin can reactivate from Admin Panel
- **If need to reset**: Delete account and have user re-register

### Task: Clean up old accounts
**Scenario**: Want to remove inactive test users

**Solution**:
1. Go to Admin Panel
2. Find inactive users
3. Click "Delete" for each one
4. Confirm deletion
5. Accounts and their jobs are removed

### Task: Temporarily block user
**Scenario**: Want to suspend user temporarily

**Solution**:
1. Go to Admin Panel
2. Click "Deactivate" on user
3. User cannot log in
4. To restore: Click "Activate"
5. User's data remains intact

## Admin Panel Features

### User List Columns
- **Username**: User's login name (shows "Admin" badge for admin user)
- **Email**: User's email address
- **Status**: "✓ Active" (green) or "✗ Inactive" (red)
- **Created**: Account creation date
- **Actions**: Activate/Deactivate/Delete buttons

### Button Behaviors

| Button | Shows For | Action |
|--------|-----------|--------|
| Activate | Inactive users (not admin) | Makes user active and able to log in |
| Deactivate | Active users (not admin) | Makes user inactive, blocks login |
| Delete | Non-admin users | Permanently removes user and all their jobs |

**Note**: Admin user (the "admin" account) cannot be deactivated or deleted for safety.

## API Usage (for Developers)

### Get All Users
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:5000/api/admin/users
```

### Activate User
```bash
curl -X POST \
  http://localhost:5000/api/admin/users/2/activate \
  -H "Authorization: Bearer <token>"
```

### Deactivate User
```bash
curl -X POST \
  http://localhost:5000/api/admin/users/2/deactivate \
  -H "Authorization: Bearer <token>"
```

### Delete User
```bash
curl -X POST \
  http://localhost:5000/api/admin/users/2/delete \
  -H "Authorization: Bearer <token>"
```

### Change Password
```bash
curl -X POST \
  http://localhost:5000/api/change-password \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "admin",
    "new_password": "newpass123",
    "confirm_password": "newpass123"
  }'
```

## Troubleshooting

### Problem: Admin user not created on startup
**Check**:
1. Is the database accessible? (Look for `reproducibility.db`)
2. Are database permissions correct? (Should be writable)
3. Are there any error messages in console?

**Solution**:
- Delete `reproducibility.db` and restart app
- Check file permissions in directory

### Problem: Cannot access Admin Panel
**Check**:
1. Are you logged in? (Look for username in navbar)
2. Is the logged-in user "admin"?
3. Is the browser showing 403 error?

**Solution**:
- Only the "admin" user can access admin panel
- Other users will get "Access Denied" error

### Problem: Cannot change password
**Check**:
1. Is old password correct?
2. Is new password at least 8 characters?
3. Do new passwords match?

**Solution**:
- Verify old password is typed correctly
- Make sure new password is 8+ characters
- Ensure confirm password matches exactly

### Problem: User cannot be deactivated/deleted
**Check**:
1. Is it the admin user?
2. Are you getting an error message?

**Solution**:
- Cannot deactivate or delete the "admin" account
- Try deactivating/deleting different user

## Tips & Best Practices

1. **Security**:
   - Change default admin password immediately
   - Use strong passwords (8+ characters)
   - Keep admin account secure

2. **User Management**:
   - Deactivate instead of deleting to preserve data
   - Only delete if data should be removed
   - Activate accounts for new registrations

3. **Monitoring**:
   - Check Admin Panel regularly
   - Remove unused/inactive accounts
   - Monitor who has access

4. **Backup**:
   - Backup `reproducibility.db` regularly
   - User deletion is permanent
   - PDFs are permanently removed

## Keyboard Shortcuts

- **Tab**: Navigate form fields
- **Enter**: Submit form or click focused button
- **Escape**: Close modals

## More Information

- Full documentation: see `ADMIN_FEATURES.md`
- Implementation details: see `IMPLEMENTATION_SUMMARY.md`
- Test suite: run `python3 test_admin_features.py`

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify admin user exists in database
3. Run test suite: `python3 test_admin_features.py`
4. Check `ADMIN_FEATURES.md` for detailed documentation
