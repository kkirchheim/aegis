# API Documentation Externalisation Plan

**Using flask-apispec + Marshmallow for automatic OpenAPI 3.0 documentation**

## Overview

Implement flask-apispec to:
- Generate OpenAPI 3.0 spec automatically
- Provide interactive Swagger UI at `/docs/`
- Validate request/response schemas
- Maintain 100% backward compatibility (routes unchanged)

---

## Phase 1: Setup & Infrastructure (30 min)

### 1.1 Install Dependencies
```bash
pip install flask-apispec apispec marshmallow
```

### 1.2 Update requirements.txt
Add to dependencies:
- flask-apispec
- apispec
- marshmallow

### 1.3 Initialize FlaskApiSpec in app.py

Near app creation (after Flask initialization):

```python
from flask_apispec import FlaskApiSpec

app = Flask(__name__)

app.config.update({
    "APISPEC_TITLE": "Paper Reproducibility Checker API",
    "APISPEC_VERSION": "1.0.0",
    "OPENAPI_VERSION": "3.0.2",
    "APISPEC_SWAGGER_URL": "/swagger/",      # Raw OpenAPI JSON
    "APISPEC_SWAGGER_UI_URL": "/docs/",      # Interactive UI
    "API_TITLE": "Paper Reproducibility Checker",
    "API_VERSION": "v1",
    "OPENAPI_BLUEPRINTS": [auth_bp, api_bp, admin_bp, jobs_bp],
})

docs = FlaskApiSpec(app)
```

### 1.4 Configure Security Scheme

```python
# In app.py, before route registration
app.config['APISPEC_SECURITY_SCHEMES'] = {
    'bearerAuth': {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'JWT'
    },
    'sessionAuth': {
        'type': 'apiKey',
        'name': 'session_id',
        'in': 'cookie'
    }
}
```

---

## Phase 2: Create Marshmallow Schemas (1.5 hrs)

Create `/schemas/` directory with modular schema files:

### 2.1 schemas/common.py

```python
from marshmallow import Schema, fields

class ErrorSchema(Schema):
    error = fields.Str(required=True)
    message = fields.Str()
    status_code = fields.Int()

class PaginationSchema(Schema):
    page = fields.Int()
    per_page = fields.Int()
    total = fields.Int()
    pages = fields.Int()

class SuccessMessageSchema(Schema):
    ok = fields.Bool(required=True)
    message = fields.Str()
```

### 2.2 schemas/auth.py

```python
from marshmallow import Schema, fields

class LoginSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=1))
    password = fields.Str(required=True, validate=validate.Length(min=6))

class RegisterSchema(Schema):
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)

class ChangePasswordSchema(Schema):
    old_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)

class SessionSchema(Schema):
    message = fields.Str()
    redirect = fields.Str()
    user_id = fields.Int()
    username = fields.Str()
```

### 2.3 schemas/jobs.py

```python
from marshmallow import Schema, fields

class JobSchema(Schema):
    id = fields.Str(required=True)
    status = fields.Str(required=True)  # pending, processing, completed, failed
    progress = fields.Float()  # 0.0-1.0
    current_stage = fields.Str()  # paper_analysis, code_execution, evaluation
    created_at = fields.DateTime()
    completed_at = fields.DateTime()
    pdf_filename = fields.Str()
    user_id = fields.Int()
    error_message = fields.Str()

class JobListSchema(Schema):
    jobs = fields.List(fields.Nested(JobSchema))
    total = fields.Int()

class JobDetailSchema(Schema):
    id = fields.Str()
    status = fields.Str()
    progress = fields.Float()
    current_stage = fields.Str()
    created_at = fields.DateTime()
    completed_at = fields.DateTime()
    pdf_filename = fields.Str()
    events = fields.List(fields.Dict())
    paper_analysis = fields.Dict()
    artifacts = fields.List(fields.Dict())
    report = fields.Dict()
    error_message = fields.Str()

class JobUploadSchema(Schema):
    """For file upload"""
    file = fields.Field(required=True, load_only=True)
```

### 2.4 schemas/chat.py

```python
from marshmallow import Schema, fields

class ChatMessageSchema(Schema):
    message = fields.Str(required=True)
    job_id = fields.Str(required=True)

class ChatMessageResponseSchema(Schema):
    role = fields.Str()  # user, assistant
    content = fields.Str()
    timestamp = fields.DateTime()

class ChatHistorySchema(Schema):
    messages = fields.List(fields.Nested(ChatMessageResponseSchema))
    total = fields.Int()
```

### 2.5 schemas/results.py

```python
from marshmallow import Schema, fields

class ArtifactSchema(Schema):
    id = fields.Str()
    job_id = fields.Str()
    url = fields.Str()
    artifact_type = fields.Str()  # code, data, model, etc.
    description = fields.Str()

class AspectEvaluationSchema(Schema):
    aspect_id = fields.Str()
    name = fields.Str()
    status = fields.Str()  # supported, unsupported, partial
    evidence = fields.Str()
    paper_supports = fields.Bool()
    code_supports = fields.Bool()
    conclusion = fields.Str()

class ExecutionResultSchema(Schema):
    step = fields.Str()
    status = fields.Str()
    output = fields.Str()
    error = fields.Str()

class PaperAnalysisSchema(Schema):
    title = fields.Str()
    abstract = fields.Str()
    extracted_text = fields.Str()
    claimed_results = fields.Dict()
    methodology = fields.Str()
    dependencies = fields.Str()
    dataset_description = fields.Str()
    citations = fields.List(fields.Dict())
```

### 2.6 schemas/admin.py

```python
from marshmallow import Schema, fields

class UserSchema(Schema):
    id = fields.Int()
    username = fields.Str()
    email = fields.Email()
    is_active = fields.Bool()
    is_admin = fields.Bool()
    created_at = fields.DateTime()
    last_login = fields.DateTime()

class UserListSchema(Schema):
    users = fields.List(fields.Nested(UserSchema))
    total = fields.Int()

class UserActionSchema(Schema):
    ok = fields.Bool()
    message = fields.Str()
    user_id = fields.Int()
```

### 2.7 schemas/__init__.py

```python
from .auth import *
from .jobs import *
from .chat import *
from .results import *
from .admin import *
from .common import *

__all__ = [
    'LoginSchema', 'RegisterSchema', 'ChangePasswordSchema', 'SessionSchema',
    'JobSchema', 'JobListSchema', 'JobDetailSchema', 'JobUploadSchema',
    'ChatMessageSchema', 'ChatHistorySchema',
    'ArtifactSchema', 'AspectEvaluationSchema', 'PaperAnalysisSchema',
    'UserSchema', 'UserListSchema',
    'ErrorSchema', 'SuccessMessageSchema',
]
```

---

## Phase 3: Annotate Routes (2 hrs)

### 3.1 Blueprint: Auth (blueprints/auth.py)

**POST /login**
```python
from flask_apispec import doc, marshal_with, use_kwargs
from schemas import LoginSchema, SessionSchema, ErrorSchema

@auth_bp.route("/login", methods=["POST"])
@doc(
    description="User login",
    tags=["Authentication"],
    responses={
        200: SessionSchema,
        400: ErrorSchema,
        401: ErrorSchema,
    }
)
@use_kwargs(LoginSchema, location="form")
@marshal_with(SessionSchema, code=200)
def login_form(**data):
    # existing logic unchanged
    ...
```

**POST /register**
```python
@auth_bp.route("/register", methods=["POST"])
@doc(
    description="User registration",
    tags=["Authentication"],
    responses={
        201: UserSchema,
        400: ErrorSchema,
        409: ErrorSchema,  # User exists
    }
)
@use_kwargs(RegisterSchema, location="form")
@marshal_with(UserSchema, code=201)
def register_user(**data):
    # existing logic unchanged
    ...
```

**POST /logout**
```python
@auth_bp.route("/logout", methods=["POST"])
@doc(
    description="User logout",
    tags=["Authentication"],
    responses={
        204: {},
        401: ErrorSchema,
    }
)
@marshal_with(None, code=204)
def logout():
    # existing logic unchanged
    ...
```

**POST /change-password**
```python
@auth_bp.route("/change-password", methods=["POST"])
@doc(
    description="Change user password",
    tags=["Authentication"],
    security=[{"sessionAuth": []}],
    responses={
        204: {},
        400: ErrorSchema,
        401: ErrorSchema,
    }
)
@use_kwargs(ChangePasswordSchema, location="json")
@marshal_with(None, code=204)
def change_password(**data):
    # existing logic unchanged
    ...
```

### 3.2 Blueprint: API - Auth Routes (blueprints/api.py)

**POST /api/auth/login, /api/auth/register, /api/auth/change-password**
- Same annotations as above but route path is `/api/auth/*`

### 3.3 Blueprint: API - Job Routes (blueprints/api.py)

**POST /api/job/upload**
```python
@api_bp.route("/job/upload", methods=["POST"])
@doc(
    description="Upload paper PDF for analysis",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    responses={
        202: JobSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        413: ErrorSchema,  # File too large
    }
)
@marshal_with(JobSchema, code=202)
def upload_pdf():
    # existing logic unchanged
    ...
```

**GET /api/job**
```python
@api_bp.route("/job", methods=["GET"])
@doc(
    description="List user's jobs",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    responses={
        200: JobListSchema,
        401: ErrorSchema,
    }
)
@marshal_with(JobListSchema, code=200)
def list_jobs_api():
    # existing logic unchanged
    ...
```

**GET /api/job/<job_id>**
```python
@api_bp.route("/job/<job_id>", methods=["GET"])
@doc(
    description="Get job details",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    params={"job_id": {"description": "Job ID", "in": "path"}},
    responses={
        200: JobDetailSchema,
        401: ErrorSchema,
        403: ErrorSchema,  # Not owner
        404: ErrorSchema,
    }
)
@marshal_with(JobDetailSchema, code=200)
def get_job_detail(job_id):
    # existing logic unchanged
    ...
```

**GET /api/job/<job_id>/full**
```python
@api_bp.route("/job/<job_id>/full", methods=["GET"])
@doc(
    description="Get full job state (for polling)",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    responses={
        200: JobDetailSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@marshal_with(JobDetailSchema, code=200)
def job_full(job_id):
    # existing logic unchanged
    ...
```

**DELETE /api/job/<job_id>**
```python
@api_bp.route("/job/<job_id>", methods=["DELETE"])
@doc(
    description="Delete job and all associated data",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    responses={
        204: {},
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@marshal_with(None, code=204)
def delete_job_route(job_id):
    # existing logic unchanged
    ...
```

### 3.4 Blueprint: API - Chat Routes (blueprints/api.py)

**POST /api/job/<job_id>/chat**
```python
@api_bp.route("/job/<job_id>/chat", methods=["POST"])
@doc(
    description="Chat about paper reproducibility",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    responses={
        200: ChatMessageResponseSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@use_kwargs(ChatMessageSchema, location="json")
@marshal_with(ChatMessageResponseSchema, code=200)
def chat_with_paper(job_id, **data):
    # existing logic unchanged
    ...
```

**GET /api/job/<job_id>/chat/history**
```python
@api_bp.route("/job/<job_id>/chat/history", methods=["GET"])
@doc(
    description="Get chat history for job",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    responses={
        200: ChatHistorySchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@marshal_with(ChatHistorySchema, code=200)
def get_chat_history_endpoint(job_id):
    # existing logic unchanged
    ...
```

**DELETE /api/job/<job_id>/chat/history**
```python
@api_bp.route("/job/<job_id>/chat/history", methods=["DELETE"])
@doc(
    description="Clear chat history for job",
    tags=["Chat"],
    security=[{"sessionAuth": []}],
    responses={
        204: {},
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@marshal_with(None, code=204)
def delete_chat_history_endpoint(job_id):
    # existing logic unchanged
    ...
```

### 3.5 Blueprint: Admin Routes (blueprints/admin.py or api.py)

**GET /api/admin/users**
```python
@doc(
    description="List all users (admin only)",
    tags=["Admin"],
    security=[{"sessionAuth": []}],
    responses={
        200: UserListSchema,
        401: ErrorSchema,
        403: ErrorSchema,
    }
)
@marshal_with(UserListSchema, code=200)
def list_users_admin():
    # existing logic unchanged
    ...
```

**POST /api/admin/users/<id>/activate**
**POST /api/admin/users/<id>/deactivate**
**POST /api/admin/users/<id>/delete**
```python
@doc(
    description="Activate/deactivate/delete user",
    tags=["Admin"],
    security=[{"sessionAuth": []}],
    responses={
        200: UserActionSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
@marshal_with(UserActionSchema, code=200)
def user_admin_action(id, action):
    # existing logic unchanged
    ...
```

### 3.6 Blueprint: System Routes (blueprints/api.py)

**GET /api/health**
```python
@api_bp.route("/health", methods=["GET"])
@doc(
    description="Health check endpoint",
    tags=["System"],
    responses={
        200: {"type": "object", "properties": {"status": {"type": "string"}}},
    }
)
@marshal_with(SuccessMessageSchema, code=200)
def health_check():
    # existing logic unchanged
    ...
```

**GET /api/cache/stats**
**DELETE /api/cache/clear**
```python
@doc(
    description="Cache statistics / clear",
    tags=["System"],
    security=[{"sessionAuth": []}],
    responses={
        200: {"type": "object"},
        401: ErrorSchema,
        403: ErrorSchema,
    }
)
def cache_operation():
    # existing logic unchanged
    ...
```

---

## Phase 4: Error Response Handling (30 min)

All error responses should follow consistent schema:

**Update all error returns to use ErrorSchema:**
```python
# Before
return jsonify({"error": "message"}), 400

# After (with schema)
@marshal_with(ErrorSchema, code=400)
# ensures consistent structure
return {"error": "message"}, 400
```

**Standard error codes documented:**
- 400: Bad Request (validation, malformed JSON)
- 401: Unauthorized (missing auth)
- 403: Forbidden (not owner, insufficient permissions)
- 404: Not Found (resource doesn't exist)
- 500: Internal Server Error

---

## Phase 5: Endpoint Registration (15 min)

### 5.1 Option A: Manual Registration

After all blueprints registered in app.py:

```python
from blueprints import auth_bp, api_bp, admin_bp, jobs_bp

app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(jobs_bp)

# Register all documented endpoints
docs.register(login_form)
docs.register(register_user)
docs.register(logout)
# ... (register all documented routes)
```

### 5.2 Option B: Auto-Discovery (recommended)

Flask-apispec can auto-discover decorated routes if configured:

```python
docs = FlaskApiSpec(app)
# Auto-registers all routes with @doc decorator
```

---

## Phase 6: Special Cases (1 hr)

### 6.1 SSE Endpoint (/events/<id>)

SSE is special - cannot use standard response schema:

```python
@api_bp.route("/events/<job_id>", methods=["GET"])
@doc(
    description="Server-sent events stream for job updates",
    tags=["Jobs"],
    security=[{"sessionAuth": []}],
    responses={
        200: {
            "description": "Event stream",
            "content": {"text/event-stream": {}}
        },
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    }
)
def job_events(job_id):
    # existing logic unchanged
    ...
```

### 6.2 File Upload (multipart/form-data)

```python
@api_bp.route("/job/upload", methods=["POST"])
@doc(
    description="Upload PDF for analysis",
    tags=["Jobs"],
    responses={202: JobSchema},
    requestBody={
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "format": "binary"}
                    },
                    "required": ["file"]
                }
            }
        }
    }
)
@marshal_with(JobSchema, code=202)
def upload_pdf():
    ...
```

### 6.3 Agent Callback Routes (Internal)

Consider whether to document or mark as internal:

```python
@api_bp.route("/agent/think", methods=["POST"])
@doc(
    description="[INTERNAL] Agent callback - do not call directly",
    tags=["Internal"],
    responses={200: {"type": "object"}},
    hidden=True,  # Don't show in Swagger UI
)
def agent_think():
    ...
```

---

## Phase 7: Testing & Iteration (1 hr)

### 7.1 Verify OpenAPI Spec

```bash
curl http://localhost:5000/swagger/ | jq .
```

Should return valid OpenAPI 3.0 spec with:
- All paths listed
- All methods documented
- Schemas defined
- Security schemes configured

### 7.2 Test Swagger UI

Open browser: `http://localhost:5000/docs/`

Verify:
- All endpoints listed in sidebar
- Descriptions readable
- Query parameters shown
- Request/response schemas visible
- "Try it out" button works

### 7.3 Validate Schemas Match Code

For each endpoint:
1. Check request schema fields match actual code usage
2. Check response schema fields match actual JSON response
3. Verify error codes match @marshal_with decorators

### 7.4 Test Request Validation

Use Swagger UI to test with:
- Valid requests → should work
- Invalid JSON → 400
- Missing required fields → 400
- Wrong types → 400
- Unauthorized → 401
- Not found → 404

---

## Implementation Order

**Recommended execution order (can be done in 2-3 sessions):**

1. **Session 1 (2.5 hrs):**
   - Phase 1: Setup (0.5 hr)
   - Phase 2: Create schemas (1.5 hrs)
   - Phase 5: Register endpoints (0.5 hr)

2. **Session 2 (2.5 hrs):**
   - Phase 3a: Annotate auth routes (0.5 hr)
   - Phase 3b: Annotate job routes (1 hr)
   - Phase 3c: Annotate chat routes (0.5 hr)
   - Phase 3d: Annotate admin routes (0.5 hr)

3. **Session 3 (2 hrs):**
   - Phase 4: Error handling (0.5 hr)
   - Phase 6: Special cases (0.5 hr)
   - Phase 7: Testing & QA (1 hr)

---

## Expected Deliverables

After implementation:

✅ OpenAPI 3.0 spec at `/swagger/`
✅ Interactive Swagger UI at `/docs/`
✅ ~25-30 documented endpoints
✅ Request/response schemas enforced
✅ Security schemes documented
✅ Error codes standardized
✅ All routes backward compatible
✅ 361/362 tests still passing

---

## Notes

- **Backward Compatibility:** All existing routes remain unchanged; we're only adding metadata
- **No Breaking Changes:** Existing API consumers unaffected
- **Zero Runtime Overhead:** Documentation is generated at startup, not per-request
- **Easy to Maintain:** Schemas are source of truth; decorators are simple
- **Version Upgrade Path:** Can version API in future using blueprints with version prefix
