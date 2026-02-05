# Flask-APISpec Migration Plan (Phase 10)

## Problem Statement
- Flask-apispec's `@marshal_with` decorator wraps ALL responses
- When endpoints use `jsonify()`, they return Response objects
- `@marshal_with` tries to serialize Response objects → **TypeError: Object of type Response is not JSON serializable**

## Root Cause
```python
# BROKEN: jsonify() returns Response object, @marshal_with tries to serialize it
@marshal_with(SessionSchema, code=200)
def api_login():
    return jsonify({"message": "Login successful"}), 200  # ← Response object
```

## Solution: Return Plain Dicts
```python
# CORRECT: Return dict tuple, @marshal_with serializes it
@use_kwargs(LoginSchema, location="json")
@marshal_with(SessionSchema, code=200)
@marshal_with(ErrorSchema, code=400)
@marshal_with(ErrorSchema, code=401)
def api_login(username, password):
    # Input validated by @use_kwargs - parameters are already validated
    user = get_user_by_username(username)
    if not user:
        return {"error": "Invalid credentials"}, 401
    return {"message": "Login successful", "redirect": "/"}, 200
```

## Key Pattern

### 1. Input Validation with `@use_kwargs`
```python
@use_kwargs(LoginSchema, location="json")
def api_login(username, password):  # ← Parameters from schema
    # No request.json parsing needed!
    # Parameters are pre-validated by schema
```

### 2. Multiple `@marshal_with` for Each Status Code
```python
@marshal_with(SessionSchema, code=200)          # Success
@marshal_with(ErrorSchema, code=400)            # Bad request
@marshal_with(ErrorSchema, code=401)            # Unauthorized
@marshal_with(ErrorSchema, code=403)            # Forbidden
@marshal_with(ErrorSchema, code=500)            # Server error
def api_login(username, password):
    # Handle all cases - each return status maps to a @marshal_with
```

### 3. Return Plain Dicts (No jsonify)
```python
# Return as (dict, status_code) tuple
return {"error": "Invalid credentials"}, 401
return {"message": "Success", "data": ...}, 200
```

## Implementation Steps

### Phase 10A: ✅ DONE
- Added input validation schemas to auth.py, admin.py, chat.py
- Exported in schemas/__init__.py

### Phase 10B: IN PROGRESS
Update endpoints by category:

#### 1. Authentication Endpoints
- `POST /api/auth/login`
  - Input: LoginSchema
  - Output: SessionSchema (200), ErrorSchema (400/401/403/500)
  
- `POST /api/auth/register`
  - Input: RegisterSchema
  - Output: SessionSchema (201), ErrorSchema (400/409/500)
  
- `POST /api/auth/change-password`
  - Input: ChangePasswordSchema
  - Output: SuccessMessageSchema (204), ErrorSchema (400/401/404/500)

#### 2. Admin Endpoints
- `GET /api/admin/users`
  - Output: UserListSchema (200), ErrorSchema (401/403/500)
  
- `PATCH /api/admin/users/<id>`
  - Input: UpdateUserStatusSchema
  - Output: UserActionSchema (200), ErrorSchema (400/401/403/404/500)
  
- `DELETE /api/admin/users/<id>`
  - Output: (204 No Content), ErrorSchema (400/401/403/404/500)
  
- `POST /api/admin/users/<id>/activate`
  - Output: UserActionSchema (200), ErrorSchema (401/403/404/500)
  
- `POST /api/admin/users/<id>/deactivate`
  - Output: UserActionSchema (200), ErrorSchema (400/401/403/404/500)
  
- `POST /api/admin/users/<id>/delete`
  - Output: UserActionSchema (200), ErrorSchema (400/401/403/404/500)

#### 3. Jobs Endpoints
- `POST /api/job/upload`
  - Output: UploadJobResponseSchema (202), ErrorSchema (400/401/413/500)
  
- `GET /api/job`
  - Output: JobListSchema (200), ErrorSchema (401/500)
  
- `GET /api/job/<id>`
  - Output: JobSchema (200), ErrorSchema (401/403/404/500)
  
- `GET /api/job/<id>/full`
  - Output: JobDetailSchema (200), ErrorSchema (401/403/404/500)
  
- `DELETE /api/job/<id>`
  - Output: (204 No Content), ErrorSchema (401/403/404/500)
  
- `GET /api/job/<id>/events`
  - Output: Custom response (200), ErrorSchema (400/401/403/404/500)

#### 4. Chat Endpoints
- `POST /api/job/<id>/chat`
  - Input: ChatMessageRequestSchema
  - Output: SuccessMessageSchema (200), ErrorSchema (400/401/403/404/500)
  
- `GET /api/job/<id>/chat/history`
  - Output: ChatHistorySchema (200), ErrorSchema (401/403/404/500)
  
- `DELETE /api/job/<id>/chat/history`
  - Output: (204 No Content), ErrorSchema (401/403/404/500)

#### 5. System Endpoints
- `GET /api/health`
  - Output: HealthResponseSchema (200/503)
  
- `GET /api/cache/stats`
  - Output: CacheStatsResponseSchema (200), ErrorSchema (401/403/500)
  
- `DELETE /api/cache/clear`
  - Output: SuccessMessageSchema (200), ErrorSchema (401/403/500)

#### 6. Agent (Internal) Endpoints
- These don't use @doc or @marshal_with (internal only)
- Still remove jsonify(), return plain dicts

### Testing
After each phase:
```bash
docker exec paper-reproducibility python3 -m pytest tests/test_app.py tests/test_auth.py -v
```

## Validation Rules (Marshmallow)

### LoginSchema
- username: required, 3-50 chars
- password: required, 8-100 chars

### RegisterSchema
- username: required, 3-50 chars
- email: required, valid email
- password: required, 8-100 chars
- confirm_password: required, must match password

### ChangePasswordSchema
- old_password: required
- new_password: required, 8-100 chars
- confirm_password: required, must match new_password

### UpdateUserStatusSchema
- is_active: required, bool

### ChatMessageRequestSchema
- message: required, 1-5000 chars

## Benefits
✅ Input validation automatic (400 Bad Request if invalid)
✅ Output serialization proper (Response objects serializable)
✅ Type safety (Marshmallow fields enforce types)
✅ OpenAPI spec generation works (no Response wrapping conflicts)
✅ Code simpler (no manual validation, no jsonify)
