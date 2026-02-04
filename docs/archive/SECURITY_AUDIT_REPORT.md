# Security Audit Report: Paper Reproducibility Checker

**Audit Date:** 2026-02-04  
**Status:** SECURITY GAPS FOUND AND DOCUMENTED  
**Priority:** HIGH - 4 Critical Issues, 2 Medium Issues

---

## Executive Summary

The Paper Reproducibility Checker application has **comprehensive authentication and authorization** for most routes, but contains **4 critical security gaps** where unprotected routes should require authentication or admin privileges.

**Overall Grade: B+ (Good foundation, but critical gaps need fixing)**

---

## Route Protection Status

### ✅ PROPERLY PROTECTED ROUTES (18 routes)

| Route | Method | Protection | Status |
|-------|--------|-----------|---------|
| `/` | GET | @require_auth | ✅ Protected |
| `/upload` | POST | @require_auth | ✅ Protected |
| `/jobs` | GET | @require_auth | ✅ Protected |
| `/job/<job_id>` | GET | @require_auth + ownership check | ✅ Protected |
| `/job/<job_id>` | DELETE | @require_auth + ownership check | ✅ Protected |
| `/history` | GET | @require_auth | ✅ Protected |
| `/profile` | GET | @require_auth | ✅ Protected |
| `/change-password` | GET | @require_auth | ✅ Protected |
| `/api/change-password` | POST | @require_auth | ✅ Protected |
| `/api/job/<job_id>/full` | GET | @require_auth + ownership check | ✅ Protected |
| `/api/job/<job_id>/chat` | POST | @require_auth + ownership check | ✅ Protected |
| `/api/job/<job_id>/chat/history` | GET | @require_auth + ownership check | ✅ Protected |
| `/api/job/<job_id>/chat/history` | DELETE | @require_auth + ownership check | ✅ Protected |
| `/events/<job_id>` | GET | @require_auth + ownership check | ✅ Protected |
| `/logout` | POST | @require_auth | ✅ Protected |
| `/admin` | GET | @require_admin | ✅ Protected |
| `/api/admin/users` | GET | @require_admin | ✅ Protected |
| `/api/admin/users/<id>/activate\|deactivate\|delete` | POST | @require_admin | ✅ Protected |

### ❌ CRITICAL SECURITY GAPS (4 routes that MUST be protected)

#### CRITICAL ISSUE #1: `/api/cache/stats` is PUBLIC (should be ADMIN ONLY)
- **Route:** `GET /api/cache/stats`
- **Current:** ❌ NO PROTECTION - Publicly accessible
- **Should be:** 🔒 `@require_admin` (admin only)
- **Risk:** Attackers can enumerate cache statistics and infer system load/activity
- **Fix Required:** Add `@require_admin` decorator
- **Lines:** ~2010-2030 in app.py

**Code Before:**
```python
@app.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    # NO PROTECTION - SECURITY GAP
```

**Code After:**
```python
@app.route("/api/cache/stats", methods=["GET"])
@require_admin
def cache_stats():
    # FIXED
```

---

#### CRITICAL ISSUE #2: `/api/cache/clear` is PUBLIC (should be ADMIN ONLY)
- **Route:** `DELETE /api/cache/clear`
- **Current:** ❌ NO PROTECTION - Publicly accessible
- **Should be:** 🔒 `@require_admin` (admin only)
- **Risk:** **CRITICAL** - Any user can delete all cached analyses, affecting all users' jobs
- **Impact:** DoS attack - wipe all analysis data
- **Fix Required:** Add `@require_admin` decorator
- **Lines:** ~2040-2070 in app.py

**Code Before:**
```python
@app.route("/api/cache/clear", methods=["DELETE"])
def cache_clear():
    # NO PROTECTION - SECURITY GAP - CRITICAL RISK
```

**Code After:**
```python
@app.route("/api/cache/clear", methods=["DELETE"])
@require_admin
def cache_clear():
    # FIXED
```

---

#### MEDIUM ISSUE #1: `/reports/<job_id>` doesn't validate ownership (HTML page)
- **Route:** `GET /reports/<job_id>`
- **Current:** ⚠️ NO OWNERSHIP CHECK - Returns HTML page without checking if user owns job
- **Should be:** Redirect to login OR check ownership and return 403
- **Risk:** Users might see job detail page for jobs they don't own
- **Status:** Page requires auth (redirects to login if not authenticated) BUT doesn't check job ownership
- **Fix Required:** Add ownership check before rendering detail page
- **Lines:** ~1865-1870 in app.py

**Code Before:**
```python
@app.route("/reports/<job_id>")
def detail_page(job_id):
    """Serve detail page for a job."""
    return render_template("detail.html", job_id=job_id)
    # NO OWNERSHIP CHECK - Frontend might reveal job data
```

**Code After:**
```python
@app.route("/reports/<job_id>")
@require_auth
def detail_page(job_id):
    """Serve detail page for a job - only for the job owner."""
    user_id = session.get('user_id')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    conn.close()
    
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403
    
    return render_template("detail.html", job_id=job_id)
```

---

#### MEDIUM ISSUE #2: `/results/<job_id>` doesn't validate ownership (alias)
- **Route:** `GET /results/<job_id>`
- **Current:** ⚠️ NO OWNERSHIP CHECK - Same as /reports/<job_id>
- **Should be:** Check ownership and return 403 if not authorized
- **Risk:** Same as above
- **Lines:** ~1872-1876 in app.py
- **Fix Required:** Same fix as /reports/<job_id>

---

## Authentication Decorators Review

### `@require_auth` Decorator ✅
- **Implementation:** Lines ~85-94
- **Status:** ✅ Correctly checks for 'user_id' in session
- **Returns:** 401 Unauthorized if not authenticated
- **Coverage:** Applied to all user-facing routes

**Code:**
```python
def require_auth(f):
    """Decorator to require authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function
```

---

### `@require_admin` Decorator ✅
- **Implementation:** Lines ~96-109
- **Status:** ✅ Correctly checks for admin privileges
- **Checks:** 'user_id' in session AND username == 'admin'
- **Returns:** 401 if not authenticated, 403 if not admin
- **Coverage:** Applied to all admin routes

**Code:**
```python
def require_admin(f):
    """Decorator to require admin authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        username = session.get('username')
        if username != 'admin':
            return jsonify({"error": "Forbidden - admin access required"}), 403
        
        return f(*args, **kwargs)
    return decorated_function
```

---

## Cross-User Access Control Review

### Job Ownership Validation ✅
All job-related routes properly validate ownership:

1. **GET /job/<job_id>** ✅
   - Lines: ~1794-1820
   - Checks: `if job["user_id"] != user_id: return 403`
   
2. **GET /api/job/<job_id>/full** ✅
   - Lines: ~1838-1885
   - Checks: `if job["user_id"] != user_id: return 403`
   
3. **DELETE /job/<job_id>** ✅
   - Lines: ~1901-1940
   - Checks: `if job["user_id"] != user_id: return 403`
   
4. **GET /events/<job_id>** ✅
   - Lines: ~1758-1785
   - Checks: `if job["user_id"] != user_id: return 403`
   
5. **POST /api/job/<job_id>/chat** ✅
   - Lines: ~2151-2190
   - Checks: `if job["user_id"] != user_id: return 403`
   
6. **GET /api/job/<job_id>/chat/history** ✅
   - Lines: ~2239-2265
   - Checks: `if job["user_id"] != user_id: return 403`
   
7. **DELETE /api/job/<job_id>/chat/history** ✅
   - Lines: ~2271-2297
   - Checks: `if job["user_id"] != user_id: return 403`

### Jobs List ✅
- **GET /jobs** - Lines: ~1811-1835
- Filters: `WHERE j.user_id = ?`
- Only shows user's own jobs

### Upload Route ✅
- **POST /upload** - Lines: ~1718-1750
- Stores: `user_id` with job
- Only authenticated users can upload

---

## Security Best Practices Review

### Session Configuration ✅
```python
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```
- ✅ Secret key is generated or loaded from env
- ✅ Secure flag set in production
- ✅ HttpOnly flag prevents JS access
- ✅ SameSite=Lax prevents CSRF

### Password Hashing ✅
```python
def hash_password(password):
    """Hash password using PBKDF2."""
    salt = secrets.token_hex(32)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwdhash.hex()}"
```
- ✅ PBKDF2 with SHA256
- ✅ 100,000 iterations (industry standard)
- ✅ Random salt per password
- ✅ Proper verification in `verify_password()`

### Database Security ✅
- ✅ Uses parameterized queries (prevents SQL injection)
- ✅ Example: `c.execute("SELECT * FROM users WHERE username = ?", (username,))`

---

## Summary of Findings

### Critical Issues (Must Fix Immediately)
| # | Route | Issue | Impact | Status |
|---|-------|-------|--------|--------|
| 1 | `/api/cache/stats` | Public (no auth) | Info disclosure | 🔴 NOT FIXED |
| 2 | `/api/cache/clear` | Public (no auth) | DoS - delete all data | 🔴 NOT FIXED |

### Medium Issues (Should Fix Soon)
| # | Route | Issue | Impact | Status |
|---|-------|-------|--------|--------|
| 3 | `/reports/<job_id>` | No ownership check | Potential data leak | 🔴 NOT FIXED |
| 4 | `/results/<job_id>` | No ownership check | Potential data leak | 🔴 NOT FIXED |

### Strengths
- ✅ All protected routes properly decorated
- ✅ All job routes validate ownership
- ✅ Proper cross-user isolation
- ✅ Strong password hashing
- ✅ Secure session configuration
- ✅ Parameterized SQL queries
- ✅ Admin routes properly restricted

---

## Recommendations

### Priority 1: CRITICAL (Fix Today)
1. **Add `@require_admin` to `/api/cache/stats`**
   - Prevents information disclosure
   - One-line fix

2. **Add `@require_admin` to `/api/cache/clear`**
   - Prevents DoS attacks
   - One-line fix

### Priority 2: HIGH (Fix This Sprint)
3. **Add ownership check to `/reports/<job_id>`**
   - Add `@require_auth` decorator
   - Add ownership validation logic
   - Return 403 if not authorized

4. **Add ownership check to `/results/<job_id>`**
   - Same fix as `/reports/<job_id>`
   - Or consolidate into single route

### Priority 3: MEDIUM (Nice to Have)
5. Consider rate limiting on:
   - `/login` (prevent brute force)
   - `/register` (prevent spam)
   - `/api/cache/clear` (prevent DoS)

6. Add audit logging for:
   - Failed login attempts
   - Admin actions
   - Sensitive data access

7. Consider CSRF protection:
   - Implement Flask-CSRF
   - Validate tokens on POST/DELETE/PUT requests

---

## Test Coverage

Comprehensive test suite provided: `tests/test_auth_security.py`

**Test Categories:**
- ✅ 18 tests: Unauthenticated access to protected routes (should return 401)
- ✅ 4 tests: Authenticated access to protected routes (should work)
- ✅ 8 tests: Cross-user access control (users can't access each other's data)
- ✅ 10 tests: Admin authorization (non-admin can't access admin routes)
- ✅ 5 tests: Public routes (accessible without auth)
- ✅ 3 tests: Critical security gaps detection

**Total: 48 security-focused test cases**

---

## Next Steps

1. **Review this report** with the security team
2. **Fix critical issues** (10 minutes):
   - Add `@require_admin` to cache routes
3. **Add ownership checks** to detail pages (20 minutes)
4. **Run test suite** to verify fixes
5. **Deploy fixes** to production
6. **Monitor** for unauthorized access attempts

---

## Conclusion

The application has a **solid authentication and authorization foundation** with proper decorators and cross-user isolation. However, **4 security gaps** need to be fixed:
- 2 critical (unprotected admin routes)
- 2 medium (missing ownership checks on detail pages)

All gaps are **easily fixable** with minimal code changes. After applying the recommended fixes, the application will achieve **A-grade security**.
