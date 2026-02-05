# OpenAPI Tags Mapping for Paper Reproducibility API

This document maps all API endpoints to their OpenAPI tags for documentation categorization.

## Overview

The Paper Reproducibility Checker API endpoints are organized into 5 main categories:

1. **Authentication** - User authentication and account management
2. **Jobs** - Job creation, listing, and management  
3. **Chat** - Chat interface with paper analysis
4. **System** - Health checks and system information
5. **Internal** - Internal agent communication (not for external clients)

## Endpoint Mappings by Tag

### Authentication (tag: "Authentication")
```
POST   /api/auth/login                    - User login
POST   /api/auth/register                 - User registration
GET    /api/auth/logout                   - User logout (via GET in auth blueprint)
POST   /api/auth/change-password          - Change user password
```

### Jobs (tag: "Jobs")
```
POST   /api/job/upload                    - Upload PDF for analysis
GET    /api/job                           - List all jobs for current user
GET    /api/job/<job_id>                  - Get job status and report
DELETE /api/job/<job_id>                  - Delete a job
GET    /api/job/<job_id>/full             - Get full job data including all details
```

### Chat (tag: "Chat")
```
POST   /api/job/<job_id>/chat             - Send message to chat with paper analysis
GET    /api/job/<job_id>/chat/history     - Get chat history for a job
DELETE /api/job/<job_id>/chat/history     - Delete chat history for a job
```

### System (tag: "System")
```
GET    /api/health                        - Health check endpoint
GET    /api/cache/stats                   - Get cache statistics (admin only)
DELETE /api/cache/clear                   - Clear all cached data (admin only)
GET    /api/job/<job_id>/events           - Get events for a job with optional timestamp filtering
```

### Internal (tag: "Internal")
These are backend-only endpoints called by the Docker agent container, not for external clients:

```
POST   /api/agent/think                   - Agent decision endpoint
POST   /api/agent/log                     - Agent logging endpoint
POST   /api/agent/execution               - Store execution details
POST   /api/agent/complete                - Report completion
```

## Implementation Notes

### Why @doc Decorators Aren't Applied

The `@doc` decorators from `flask_apispec` have compatibility issues with several endpoints that return tuple responses like `return jsonify(...), status_code`. The flask_apispec response marshaling attempts to serialize Response objects directly, which causes TypeError exceptions.

The endpoints have been documented with inline comments specifying their intended OpenAPI tags. A complete implementation would require either:

1. **Refactoring endpoints** to return plain dicts instead of jsonified responses
2. **Using flask-restx** instead of flask-apispec for better compatibility
3. **Configuring apispec** with proper response schemas and marshaling rules

### Verification

To verify the API tags are properly categorized:

```bash
# Check health of API
curl http://localhost:5000/api/health

# Test authentication endpoints
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'

# List jobs (requires authentication)
curl http://localhost:5000/api/job \
  -H "Cookie: session=<session_id>"
```

### HTML Routes (Not Documented in OpenAPI)

The following routes serve HTML templates and should NOT be included in OpenAPI documentation:

**Authentication Routes (blueprints/auth.py):**
- GET /login
- GET /register
- GET /profile
- GET /change-password

**Job Routes (blueprints/jobs.py):**
- GET /jobs
- GET /job/<job_id>
- GET /history
- GET / (home page)

These are HTML page routes and have no @doc decorators applied.

## Future Improvements

1. Migrate from flask-apispec to flask-restx for better OpenAPI support
2. Refactor endpoints to use a consistent response pattern compatible with apispec
3. Generate OpenAPI spec without relying on response marshaling
4. Add OpenAPI examples and detailed response schemas for each endpoint
5. Document authentication requirements in the OpenAPI spec

