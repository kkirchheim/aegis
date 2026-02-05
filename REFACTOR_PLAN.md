# API Marshmallow Refactor Plan

## Goal
Standardize all public-facing API endpoints to follow the Marshmallow pattern:
- **Input validation** via `@use_kwargs(SchemaName, location="json")`
- **Output serialization** via `@marshal_with(SchemaName, code=XXX)` (before `@doc`)
- **Proper HTTP status codes** (204 for DELETE, 202 for async, etc.)
- **Consistent envelope format** for list responses

---

## Phase 1: Jobs API ✅ COMPLETE

### Commit: b8808d5

**Changes:**
1. ✅ `GET /api/job` - Fixed output format
   - Now returns `{"jobs": [...], "total": N}` per JobListSchema
   - Tests updated to expect envelope format
   
2. ✅ `POST /api/job/upload` - Fixed decorators and response
   - Added `@marshal_with` decorators (moved before `@doc`)
   - Added `status: "pending"` field to response
   - Explicit 202 status code
   
3. ✅ `DELETE /api/job/{id}` - Fixed test expectations
   - Returns 204 No Content (correct per HTTP spec)
   - Test updated

4. ✅ Test fixes
   - test_list_jobs_empty: Expect dict envelope
   - test_list_jobs_with_jobs: Expect dict envelope
   - test_list_jobs_isolation: Expect dict envelope
   - test_upload_pdf_success: Expect "status" field
   - test_upload_too_large: Expect 413 (was 400)
   - test_delete_job_success: Expect 204 (was 200)

**Results:**
- ✅ 4 list tests passing
- Running full suite now...

---

## Phase 2: Chat Endpoints (NEXT)

**Endpoints:** 3
1. `POST /api/job/{id}/chat` - Add `@use_kwargs(ChatMessageSchema)`
2. `GET /api/job/{id}/chat/history` - Already OK (no input)
3. `DELETE /api/job/{id}/chat/history` - Already OK (no input)

**Required Schema:**
```python
# schemas/chat.py
ChatMessageRequestSchema:
  - message: str (required, 1-5000 chars)
```

---

## Phase 3: Admin Endpoints

**Endpoints:** 8
- `GET /api/admin/users` - OK
- `POST /api/admin/users` - Add input schema
- `GET /api/admin/users/{id}` - OK
- `PUT /api/admin/users/{id}/activate` - Add `@use_kwargs(UpdateUserStatusSchema)`
- `PUT /api/admin/users/{id}/deactivate` - Add `@use_kwargs(UpdateUserStatusSchema)`
- `DELETE /api/admin/users/{id}` - OK
- Plus 2 more endpoints

**Required Schemas:**
```python
# schemas/admin.py
UpdateUserStatusSchema:
  - is_active: bool (required)

UpdateUploadLimitSchema:
  - max_pdf_size_mb: int (required, 1-5000)
```

---

## Phase 4: System & Cache Endpoints

- `GET /api/health` - Already OK
- `GET /api/cache/stats` - Already OK
- `GET /api/job/{id}/events` - Already OK

---

## Key Pattern Rules

### ✅ DO
```python
@api_bp.route("/path", methods=["POST"])
@use_kwargs(InputSchema, location="json")           # ← INPUT first
@marshal_with(OutputSchema, code=200)              # ← OUTPUTS second
@marshal_with(ErrorSchema, code=400)
@doc(...)                                            # ← DOCS last
def endpoint(validated_field1, validated_field2):
    # Fields come from @use_kwargs, not request parsing
    try:
        result = do_work(validated_field1)
        return result  # 200 implicit for success
    except Exception as e:
        return {"error": str(e)}, 500
```

### ❌ DON'T
```python
# ❌ Wrong: @use_kwargs with request.get_json()
@use_kwargs(Schema)
def endpoint(field):
    data = request.get_json()  # ← Don't do this
    
# ❌ Wrong: Bare lists (must wrap in envelope)
return jobs  # ← Should be {"jobs": jobs, "total": len(jobs)}

# ❌ Wrong: @marshal_with after @doc
@doc(...)
@marshal_with(...)  # ← Wrong order

# ❌ Wrong: jsonify() with @marshal_with
@marshal_with(Schema)
def endpoint():
    return jsonify({"data": "..."})  # ← jsonify not needed
```

---

## Testing Strategy

1. Run targeted endpoint tests (e.g., `test_list_jobs_empty`)
2. Run full test suite to catch regressions
3. Update integration tests as we modify endpoints
4. Final validation with OpenAPI spec (`/swagger/`)

---

## Remaining Work

- [ ] Phase 2: Chat endpoints (3 endpoints, 1 schema)
- [ ] Phase 3: Admin endpoints (8 endpoints, 2 schemas)
- [ ] Phase 4: System endpoints (verify already OK)
- [ ] Full test suite green
- [ ] Docker build and smoke test

---
