# Phase 1: Aspect Plugin System Implementation

## Overview
Implementation of the aspect plugin system for the paper reproducibility checker. This provides a framework for defining, managing, and applying reproducibility evaluation criteria across multiple users.

## What Was Implemented

### 1. Models (`models/aspect.py`)
- **Aspect**: Global template (shared across all users)
  - Fields: id (UUID), name, description, prompt, is_default, created_at, updated_at
  - Cannot be deleted if is_default=True
  - Indexed on is_default for efficient queries

- **UserAspect**: Per-user instance of an aspect
  - Fields: id (UUID), user_id (FK), aspect_id (FK), is_active, custom_prompt, deleted_at, created_at, updated_at
  - Unique constraint: (user_id, aspect_id)
  - Soft delete support via deleted_at field
  - Supports prompt override per user

### 2. Repositories (`repositories/aspect_repository.py`)

**AspectRepository** - Global aspect management:
- `get_aspect(aspect_id)` - Retrieve by ID
- `get_all_aspects()` - Get all aspects
- `get_default_aspects()` - Get only default aspects
- `create_aspect(name, description, prompt, is_default)` - Create new aspect
- `update_aspect(aspect_id, name, description, prompt)` - Update aspect
- `delete_aspect(aspect_id)` - Delete (raises AspectDeletionError if default)

**UserAspectRepository** - Per-user aspect management:
- `get_user_aspects(user_id)` - Get all aspects for user
- `get_active_aspects(user_id)` - Get only active aspects (with JOIN)
- `get_user_aspect(user_id, aspect_id)` - Get specific user aspect
- `create_user_aspect(user_id, aspect_id, custom_prompt)` - Create user aspect
- `update_user_aspect(user_id, aspect_id, is_active, custom_prompt)` - Update settings
- `delete_user_aspect(user_id, aspect_id)` - Soft delete

### 3. Service Layer (`services/aspect_service.py`)

**AspectService** - Business logic for aspect management:
- `get_or_create_default_aspects(user_id)` - Seed 3 default aspects for new users (idempotent)
- `get_all_aspects_for_user(user_id)` - Returns list with all user aspects
- `create_custom_aspect(user_id, name, description, prompt)` - Create custom aspect
- `update_custom_aspect(user_id, aspect_id, name, description, prompt)` - Update custom aspect
- `delete_custom_aspect(user_id, aspect_id)` - Delete custom aspect (only non-defaults)
- `activate_aspect(user_id, aspect_id)` - Activate aspect
- `deactivate_aspect(user_id, aspect_id)` - Deactivate aspect
- `override_prompt(user_id, aspect_id, custom_prompt)` - Override default prompt
- `get_active_aspects_for_evaluation(user_id)` - Get active aspects with prompts (custom if set, else default)

**Default Aspects** (seeded for all new users):
1. Code Availability - Is the code publicly available?
2. Dependency Documentation - Are all dependencies documented?
3. Reproducibility - Can the results be reproduced?

### 4. Exception Handling (`services/exceptions.py`)
- `AspectNotFoundError` - Aspect does not exist
- `AspectDeletionError` - Attempt to delete/modify default aspect
- `UserAspectNotFoundError` - User does not have this aspect
- `DuplicateAspectError` - User already has this aspect (reserved for future use)

### 5. Tests

**Test Coverage: 55 Tests Total**

#### `tests/test_aspect_models.py` (10 tests)
- ✅ Aspect creation with all fields
- ✅ Aspect is_default defaults to False
- ✅ Timestamps auto-set (created_at, updated_at)
- ✅ Multiple aspect creation isolation
- ✅ UserAspect creation
- ✅ UserAspect custom_prompt nullable
- ✅ UserAspect unique constraint violation
- ✅ Multiple aspects per user
- ✅ is_active defaults to True
- ✅ Soft delete with deleted_at

#### `tests/test_aspect_repositories.py` (26 tests)

**AspectRepository (13 tests):**
- ✅ Create aspect
- ✅ Create default aspect
- ✅ Get aspect by ID
- ✅ Get non-existent aspect returns None
- ✅ Get all aspects
- ✅ Get only default aspects
- ✅ Update aspect
- ✅ Update partial fields
- ✅ Update non-existent aspect
- ✅ Delete non-default aspect succeeds
- ✅ Delete default aspect raises AspectDeletionError
- ✅ Delete non-existent aspect
- ✅ Multiple aspect isolation

**UserAspectRepository (13 tests):**
- ✅ Create user aspect
- ✅ Create with custom prompt
- ✅ Get user aspect by ID
- ✅ Get non-existent aspect
- ✅ Get all aspects for user
- ✅ Get only active aspects
- ✅ Exclude soft-deleted aspects
- ✅ Update is_active flag
- ✅ Update custom_prompt
- ✅ Update both fields
- ✅ Soft delete aspect
- ✅ Delete non-existent aspect
- ✅ Multiple users isolated

#### `tests/test_aspect_service.py` (19 tests)

**Service Logic (12 tests):**
- ✅ Seed defaults on first user (creates 3)
- ✅ Seed defaults idempotent (no duplicates)
- ✅ Get all aspects for user
- ✅ Create custom aspect
- ✅ Update custom aspect
- ✅ Update default aspect fails
- ✅ Delete custom aspect
- ✅ Delete default aspect fails
- ✅ Activate aspect
- ✅ Deactivate aspect
- ✅ Override prompt
- ✅ Get active aspects for evaluation

**Advanced Features (7 tests):**
- ✅ Get active aspects uses custom_prompt when set
- ✅ Get active aspects uses default prompt when no custom
- ✅ Get active aspects excludes inactive
- ✅ Full workflow integration (seed → create → override → evaluate)
- ✅ Multiple users isolated
- ✅ Default aspects cannot be modified via service
- ✅ Prompt overrides independent per user

## Architecture Highlights

### 1. Follows Existing Patterns
- Peewee ORM models with BaseModel
- UUID primary keys (consistent with APIKey model)
- DateTime fields with default=datetime.now
- Repository layer for data access
- Service layer for business logic
- Custom exceptions for error handling

### 2. Key Design Decisions

**Unique Constraint on (user_id, aspect_id)**
- Ensures one entry per user per aspect
- Enforced at database level via Peewee indexes

**Soft Delete for UserAspect**
- Preserves history via deleted_at field
- Allows audit trails without hard deletes
- get_active_aspects filters on deleted_at.is_null()

**Idempotent Seeding**
- get_or_create_default_aspects checks if aspect exists before creating
- Safe to call multiple times without duplicating
- Uses aspect name as identifier for check

**Prompt Override Strategy**
- Custom prompt stored per user (UserAspect.custom_prompt)
- Default prompt in global Aspect
- get_active_aspects_for_evaluation returns custom if set, else default
- Allows per-user customization without modifying shared aspect

**User Isolation**
- All queries filtered by user_id
- Multiple users can have same aspect with different configurations
- Changes to one user's settings don't affect others

### 3. Database Integration
- Updated `models/database.py` to include Aspect and UserAspect in init_db()
- Both models use BaseModel and existing db connection
- Safe table creation with safe=True parameter
- Proper foreign key relationships to User model

## Testing Strategy

### Fixture-Based Testing
- Uses pytest fixtures for consistent test setup
- Each test gets fresh database via conftest.py
- app fixture provides Flask context for database operations
- User creation via User.create() for FK consistency

### Comprehensive Coverage
- **Unit tests**: Model validation and repository operations
- **Integration tests**: Full workflows across service layer
- **Edge cases**: Unique constraints, soft deletes, error handling
- **Isolation**: Multiple user scenarios, aspect state independence

### Error Path Testing
- Attempting to delete default aspects (raises AspectDeletionError)
- Attempting to modify default aspects
- Non-existent aspect/user handling
- Unique constraint violations

## How to Run Tests

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Or use Docker
docker-compose build
```

### Run All Aspect Tests
```bash
# Run all aspect tests
python -m pytest tests/test_aspect_*.py -v

# Run specific test file
python -m pytest tests/test_aspect_models.py -v
python -m pytest tests/test_aspect_repositories.py -v
python -m pytest tests/test_aspect_service.py -v

# Run with coverage
python -m pytest tests/test_aspect_*.py --cov=models.aspect --cov=repositories.aspect_repository --cov=services.aspect_service

# Run with short traceback
python -m pytest tests/test_aspect_*.py -v --tb=short
```

### Verify Imports
```bash
python -c "from models.aspect import Aspect, UserAspect; from repositories.aspect_repository import AspectRepository, UserAspectRepository; from services.aspect_service import AspectService; print('✅ All imports OK')"
```

## Implementation Checklist

- ✅ Models (Aspect, UserAspect) with all required fields
- ✅ AspectRepository with all required methods
- ✅ UserAspectRepository with all required methods
- ✅ AspectService with all required methods
- ✅ Custom exceptions (AspectNotFoundError, AspectDeletionError, UserAspectNotFoundError, DuplicateAspectError)
- ✅ Default aspects seeding (3 defaults)
- ✅ Comprehensive tests (55 tests)
- ✅ Test coverage for all major flows
- ✅ Edge case handling
- ✅ User isolation and multi-user scenarios
- ✅ Integration with existing codebase patterns
- ✅ Git commit on feature branch

## Files Created/Modified

### New Files
- `models/aspect.py` - Aspect and UserAspect models
- `repositories/aspect_repository.py` - Data access layer
- `repositories/__init__.py` - Package marker
- `services/aspect_service.py` - Business logic
- `services/exceptions.py` - Custom exceptions
- `tests/test_aspect_models.py` - Model tests
- `tests/test_aspect_repositories.py` - Repository tests
- `tests/test_aspect_service.py` - Service tests

### Modified Files
- `models/database.py` - Added Aspect and UserAspect to init_db()

## Next Steps (Phase 2)

Suggested follow-up work:
1. API endpoints for aspect management
2. User interface for aspect configuration
3. Integration with evaluation pipeline
4. Aspect evaluation execution
5. Results aggregation by aspect

## Notes

- All code follows existing codebase patterns and style
- Type hints used throughout for clarity
- Docstrings provided for all public methods and classes
- Error handling uses custom exceptions (not assertions)
- Tests are isolated and don't depend on execution order
- Database usage follows existing Peewee ORM patterns
