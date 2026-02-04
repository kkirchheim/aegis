# Changelog

All notable changes to the Paper Reproducibility Checker.

## [0.3.0] - 2026-02-03

### Added
- **15 Reproducibility Aspects** - Comprehensive evaluation across 3 tiers (Critical/High/Nice-to-Have)
- **Multi-Source Evaluation** - Claude compares paper claims vs code implementation vs execution
- **Professional UI** - Tailwind CSS + DaisyUI with dark mode, responsive design
- **Reproducibility Checklist** - Tier-grouped aspects with collapsible evidence sections
- **Aspect Evidence** - Shows paper support, code support, and reasoning for each metric
- **Advanced Agent Capabilities**:
  - `check_for_tests()` - Detects test files and patterns
  - `check_for_randomness_seeds()` - Scans for seed initialization
  - Enhanced `get_installed_packages()` - Reads requirements.txt + shows contents
- **Event Persistence** - All SSE events stored in database for retrieval
- **Evaluation Stage** - Automatic multi-source evaluation after agent completes
- **Dark Mode** - Theme toggle with localStorage persistence
- **Organized Documentation** - `/docs/` folder with API, Architecture, Development, Deployment, Troubleshooting guides

### Changed
- **Output Window:** 300 → 2000 characters (prevents truncation of completion messages)
- **Docker Cleanup:** `remove=True` → manual cleanup with try/finally (prevents race conditions)
- **UI Framework:** Custom CSS → Tailwind + DaisyUI
- **Delete Workflow:** Delete button on each job + detail page with confirmation modal
- **Report Layout:** Extensive restructure with DaisyUI components and better visual hierarchy

### Fixed
- **Agent Loop Prevention:** Agent no longer loops after seeing truncated output
- **Container Race Condition:** Proper cleanup prevents "404 container not found" errors
- **Delete Modal:** Native DaisyUI dialog instead of custom styled div
- **Mobile Responsiveness:** Grid layouts now auto-fit on smaller screens

### Docs
- Created `/docs/API.md` - Complete API reference
- Created `/docs/ARCHITECTURE.md` - System design and data flow
- Created `/docs/DEVELOPMENT.md` - Development setup, testing, contribution workflow
- Created `/docs/DEPLOYMENT.md` - Production deployment, scaling, monitoring
- Created `/docs/TROUBLESHOOTING.md` - Common issues and solutions
- Updated `README.md` with comprehensive project documentation
- Moved legacy docs (`AGENT_CONTAINER.md`, `STAGE2_*`) to archive

---

## [0.2.0] - 2026-02-01

### Added
- **Docker Agent Execution** - Sandboxed code execution in isolated containers
- **Execution Details Capture** - Commands run, output, actual results, dependencies
- **Agent Communication API**:
  - `/api/agent/think` - Agent asks Claude for decisions
  - `/api/agent/log` - Agent logs progress
  - `/api/agent/execution` - Submit execution details
  - `/api/agent/complete` - Report success/failure
- **Container Resource Limits** - 2GB RAM, 2 CPU cores, 300s timeout per command
- **Docker Networking** - All containers on `workspace_traefik` network
- **Comprehensive Test Suite** - 11 tests covering None value edge cases and API validation
- **Test Documentation** - `TESTING.md` with debugging and contributing guidelines
- **Agent Container Documentation** - `AGENT_CONTAINER.md` with container specs and improvements

### Changed
- **Agent Loop** - Now asks Claude for next action on each iteration (up to 15 max)
- **Error Handling** - Tracks errors, shows last 2 in prompt to Claude
- **Session Invalidation** - Fixed session contamination between challenge switching

### Fixed
- **NoneType Crash** - Pattern `get("key") or []` prevents None value crashes
- **JSON Parsing** - Implemented 4 parsing methods (direct, ```json block, plain code, substring)
- **CSRF Token** - Mobile users no longer get "token missing" errors
- **Docker Build** - All dependencies now installed correctly

---

## [0.1.0] - 2026-01-31

### Added
- **Initial Release** - MVP Paper Reproducibility Checker
- **PDF Upload & Processing** - Accepts papers up to 100MB, extracts text
- **Claude-Powered Parsing** - Analyzes paper to identify:
  - Code artifacts (GitHub repos, datasets)
  - Reproducibility aspects (documentation, hyperparameters, datasets)
  - Methodology and claims
- **Real-Time Progress Updates** - Server-Sent Events (SSE) stream to frontend
- **Job History** - Browse all uploaded papers with status
- **Responsive Web UI** - Upload form, progress log, job list
- **SQLite Database** - Persistent storage (jobs, artifacts, reports)
- **Docker Compose Setup** - Multi-container orchestration with Flask + Redis

### Features
- Drag-and-drop PDF upload
- Live progress indicator with percentage
- EventSource API for real-time updates
- Clean, modern web interface
- Job persistence and retrieval

---

## [0.0.1] - 2026-01-20 (Pre-Release)

### Initial Development
- Project scaffolding
- Architecture design
- Technology stack selection (Flask + Docker + Claude API)
- Initial documentation

---

## Version Schema

We use **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`

- **MAJOR** - Breaking changes, major features (0 → 1 when production-ready)
- **MINOR** - New features, backwards compatible (agent execution, UI redesign)
- **PATCH** - Bug fixes, security patches (NoneType fix, race condition fix)

## Release Schedule

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 0.3.0 | Feb 3, 2026 | Current | 15 aspects, professional UI, production-ready |
| 0.2.0 | Feb 1, 2026 | Stable | Agent execution, comprehensive testing |
| 0.1.0 | Jan 31, 2026 | Stable | Initial release, MVP features |

## Upgrade Path

### 0.1 → 0.2
- Breaking: Agent API endpoints now required
- Breaking: Docker container spawning mandatory
- Upgrade: Run `docker-compose build` and `docker-compose down -v` (resets DB)

### 0.2 → 0.3
- Non-breaking: New evaluation stage is automatic
- Non-breaking: UI changes backwards compatible
- Upgrade: `docker-compose build` then `docker-compose restart`
- Database: Auto-migrates (no action needed)

### 0.3 → 1.0 (Future)
- Production stability (security audit)
- Kubernetes support
- Multi-database backend (PostgreSQL, MongoDB)
- Authentication system
- Advanced monitoring

## Known Issues

### Current (0.3.0)
- [ ] SQLite not suitable for 100+ concurrent users (use PostgreSQL)
- [ ] No authentication system (add JWT in v1.0)
- [ ] No rate limiting on production (use Redis backend)

### Fixed
- ~~Agent infinite loop on truncated output~~ ✅ Fixed in 0.3.0
- ~~NoneType crashes in agent think endpoint~~ ✅ Fixed in 0.2.0
- ~~Container race condition on cleanup~~ ✅ Fixed in 0.3.0

## Deprecations

### 0.2.0
- Old STAGE files (`STAGE2_*`) - Use `/docs/` instead
- Legacy Agent Container docs - Consolidated to `DEVELOPMENT.md`

## Contributing

See [DEVELOPMENT.md](/docs/DEVELOPMENT.md) for:
- Code style and conventions
- Test requirements
- Git workflow
- Commit message format

## Security

See [DEPLOYMENT.md](/docs/DEPLOYMENT.md) for production security hardening.

## Migration Notes

### v0.2→v0.3 Database (Optional)
SQLite → PostgreSQL (recommended for production):

```bash
# Backup existing data
sqlite3 reproducibility.db ".dump" > backup_v0.2.sql

# Update docker-compose with PostgreSQL service
# Update app.py DATABASE_URL
# Run: docker-compose up -d

# Data migrates automatically on first run
```

---

**Latest:** 0.3.0 (Feb 3, 2026)  
**Status:** Production-Ready  
**Repository:** https://github.com/kkirchheim/paper-reproducibility
