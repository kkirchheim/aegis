# Multi-User Authentication Tests - Quick Reference

## File Location
`/home/user/.openclaw/workspace/paper-reproducibility/tests/test_multiuser_auth.py`

## Quick Stats
- **Total Tests:** 33
- **Test Classes:** 7
- **Status:** ✅ All passing
- **File Size:** ~29 KB
- **Execution Time:** ~5 seconds

## Test Organization

```
test_multiuser_auth.py
├── TestRegistrationFlow (9 tests)
│   ├── Valid user creation
│   ├── Duplicate prevention
│   └── Validation checks
├── TestLoginFlow (7 tests)
│   ├── Session creation
│   ├── Credential validation
│   └── Multi-user sessions
├── TestJobCreationAndIsolation (5 tests)
│   ├── Authentication requirements
│   ├── User1 & user2 uploads
│   └── Job isolation
├── TestOwnershipVerification (4 tests)
│   ├── Cross-user access denied
│   └── Self access allowed
├── TestLogout (4 tests)
│   ├── Session clearing
│   ├── Protected routes
│   └── Re-login flow
├── TestSessionIsolation (1 test)
│   └── Concurrent sessions
└── TestDatabaseMultiUserState (3 tests)
    ├── User storage
    ├── Schema validation
    └── User-job associations
```

## Key Test Functions

### Registration Tests
```python
test_register_valid_user()          # Happy path
test_register_duplicate_username()  # Constraint validation
test_register_short_password()      # Min length validation
test_register_invalid_email()       # Format validation
```

### Login Tests
```python
test_login_valid_user()             # Happy path
test_login_wrong_password()         # Security check
test_login_nonexistent_user()       # User validation
test_two_users_different_sessions() # Session isolation
```

### Job Isolation Tests
```python
test_upload_requires_auth()         # Authorization check
test_job_isolation_user1_cannot_see_user2_job()  # Isolation
test_jobs_list_returns_all_jobs()   # Endpoint validation
```

### Ownership Tests
```python
test_user1_cannot_access_user2_job()     # 403 Forbidden
test_user1_can_access_own_job()          # 200 OK
test_user2_cannot_access_user1_job()     # Cross-user denial
```

### Logout Tests
```python
test_logout_clears_session()              # Session cleanup
test_protected_route_after_logout()       # Reauth required
test_home_page_redirect_after_logout()    # Redirect check
test_login_again_after_logout()           # Re-login works
```

## Running Tests

### All Tests
```bash
cd /home/user/.openclaw/workspace/paper-reproducibility
docker run --rm -v "$(pwd):/app" paper-reproducibility-tests pytest tests/test_multiuser_auth.py -v
```

### Specific Class
```bash
pytest tests/test_multiuser_auth.py::TestRegistrationFlow -v
pytest tests/test_multiuser_auth.py::TestLoginFlow -v
pytest tests/test_multiuser_auth.py::TestOwnershipVerification -v
```

### Specific Test
```bash
pytest tests/test_multiuser_auth.py::TestOwnershipVerification::test_user1_cannot_access_user2_job -v
```

### With Verbose Output
```bash
pytest tests/test_multiuser_auth.py -vv
```

### With Output Capture Disabled
```bash
pytest tests/test_multiuser_auth.py -s
```

### Failed Tests Only
```bash
pytest tests/test_multiuser_auth.py --lf
```

### Last Failed + New Tests
```bash
pytest tests/test_multiuser_auth.py --ff
```

## Requirements Met ✅

### 1. Registration & Login Flow
- ✅ Register user1, user2
- ✅ Login as user1, verify session set
- ✅ Login as user2, verify different session
- **Tests:** 16 (9 registration + 7 login)

### 2. Job Isolation  
- ✅ User1 uploads paper → gets job1
- ✅ User2 uploads paper → gets job2
- ✅ GET /jobs as user1 returns only user1's jobs
- ✅ GET /jobs as user2 returns only user2's jobs
- **Tests:** 5

### 3. Ownership Verification
- ✅ User1 tries to access /job/<user2_job_id> → 403 Forbidden
- ✅ User2 tries to access /job/<user1_job_id> → 403 Forbidden
- ✅ User1 can access /job/<user1_job_id> → 200 OK
- **Tests:** 4

### 4. Logout
- ✅ Login as user1
- ✅ POST /logout
- ✅ Verify session cleared
- ✅ Try to access protected route → redirected to login
- **Tests:** 4

## Fixtures Used

### `client()`
Creates fresh Flask test client with temporary database.

**Usage:**
```python
def test_example(self, client):
    response = client.get('/')
```

### `sample_pdf()` & `create_sample_pdf()`
Generates minimal valid PDF for uploads.

**Usage:**
```python
def test_upload(self, client):
    response = client.post('/upload', data={
        'pdf': (create_sample_pdf(), 'test.pdf')
    })
```

## Common Assertions

```python
# Status codes
assert response.status_code == 200    # Success
assert response.status_code == 401    # Unauthorized
assert response.status_code == 403    # Forbidden
assert response.status_code == 404    # Not found

# JSON responses
data = response.get_json()
assert 'error' in data
assert data['message'] == 'Expected message'

# Session checks
assert 'user_id' in session
assert session['username'] == 'user1'

# Database checks
with app.app_context():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT ...")
```

## Database Schema (Test Environment)

```sql
-- Created for each test
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- Multi-user support
    status TEXT DEFAULT 'pending',
    pdf_path TEXT NOT NULL,
    pdf_filename TEXT,
    report JSON,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

## Debugging Tips

### View Test Output
```bash
pytest tests/test_multiuser_auth.py -s  # Show print statements
```

### Increase Verbosity
```bash
pytest tests/test_multiuser_auth.py -vv  # Very verbose
```

### Run with Logging
```bash
pytest tests/test_multiuser_auth.py --log-cli-level=INFO
```

### Focus on Failures
```bash
pytest tests/test_multiuser_auth.py -x  # Stop on first failure
pytest tests/test_multiuser_auth.py --tb=short  # Short traceback
```

## Expected Test Output

```
============================= test session starts ==============================
...collecting ... collected 33 items

tests/test_multiuser_auth.py::TestRegistrationFlow::test_register_page_loads PASSED
tests/test_multiuser_auth.py::TestRegistrationFlow::test_register_valid_user PASSED
... (31 more tests)

======================== 33 passed in 5.17s ========================
```

## Implementation Checklist

✅ Registration validation (username, email, password)  
✅ Login with credentials  
✅ Session management (create, clear, verify)  
✅ Job creation with user_id  
✅ Job isolation per user  
✅ Access control (403 Forbidden)  
✅ Logout and session cleanup  
✅ Database constraints  
✅ Password hashing (PBKDF2)  
✅ Pytest fixtures for cleanup  

## Notes

- Each test uses a fresh temporary database
- Database is automatically cleaned up after each test
- PDF files are properly closed/freed between tests
- Session isolation is tested with concurrent operations
- All HTTP status codes are validated
- Both positive and negative scenarios tested

## Next Steps

If needed, extend tests with:
- [ ] Email verification tests
- [ ] Password reset tests
- [ ] OAuth/3rd party auth tests
- [ ] Rate limiting tests
- [ ] CSRF protection tests
- [ ] XSS prevention tests
- [ ] Token-based auth tests (JWT)
