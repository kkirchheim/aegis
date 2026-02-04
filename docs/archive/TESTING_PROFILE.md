# Profile Page - Testing Guide

## Quick Test Steps

### 1. Start the Application
```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
# Start your Flask app (however you normally do it)
python app.py  # or appropriate startup command
```

### 2. Test: Access Without Authentication
- **Test**: Navigate to `http://localhost:5000/profile` without logging in
- **Expected**: Should redirect to login page
- **Status**: ✓ Protected by `@require_auth` decorator

### 3. Test: Login and View Profile
- **Test**: Log in with valid credentials
- **Test**: Click user menu dropdown (👤 icon in navbar)
- **Test**: Click "Profile" link
- **Expected**: 
  - Profile page loads
  - Username displays
  - Email displays (if available)
  - Account created date displays (formatted)
  - Page supports dark mode toggle

### 4. Test: Password Change Form
- **Test**: Fill out password change form with:
  - Current password (correct)
  - New password (min 8 chars)
  - Confirm password (matching)
- **Test**: Click "Change Password" button
- **Expected**:
  - Success message displays
  - Page redirects to home after 2 seconds
  - New password works on next login

### 5. Test: Password Change Validation
- **Test A - Mismatched passwords**:
  - Enter non-matching new/confirm passwords
  - Expected: Client-side error shows
  
- **Test B - Too short password**:
  - Enter password < 8 characters
  - Expected: Client-side error shows
  
- **Test C - Wrong current password**:
  - Enter incorrect current password
  - Expected: API returns error "Current password is incorrect"
  
- **Test D - Empty fields**:
  - Leave any field empty and submit
  - Expected: Browser validation prevents submission

### 6. Test: Dark Mode
- **Test**: Toggle theme button (🌙/☀️) in navbar
- **Expected**: Page switches between light/dark theme
- **Test**: Refresh page
- **Expected**: Theme preference persists

### 7. Test: Navigation
- **Test**: From profile page, click "← Back to Home"
- **Expected**: Returns to home page
- **Test**: From profile page, use navbar to navigate to other sections
- **Expected**: All navbar links work correctly

## Manual Testing Checklist

- [ ] Can access /profile when logged in
- [ ] Cannot access /profile when logged out (redirects to login)
- [ ] Username displays correctly
- [ ] Email displays correctly (if set)
- [ ] Created at date displays in readable format
- [ ] Password change form validates passwords match
- [ ] Password change form validates min 8 characters
- [ ] Current password verification works
- [ ] Successful password change shows success message
- [ ] Failed password change shows error message
- [ ] Page redirects to home after successful password change
- [ ] Dark mode toggle works
- [ ] Theme persists after page refresh
- [ ] All navbar links work
- [ ] "Profile" link appears in user dropdown menu
- [ ] Mobile responsive design works

## Key URLs

- Profile page: `http://localhost:5000/profile`
- Password change API: `POST http://localhost:5000/api/change-password`

## Code References

1. **Template**: `templates/profile.html` (11 KB)
   - Includes navbar
   - Displays user info
   - Password change form
   - Dark mode support

2. **Route**: `app.py` line 1477
   - GET /profile endpoint
   - @require_auth decorator
   - Fetches user data
   - Formats created_at date

3. **Navbar**: `templates/navbar.html` line 51
   - Profile link in dropdown
   - Points to /profile

4. **Existing API**: `app.py` (around line 1440)
   - POST /api/change-password
   - Validates passwords
   - Updates database
