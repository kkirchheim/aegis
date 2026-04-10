# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Artifact Review — a Flask web app that analyzes academic papers for reproducibility. It runs a three-stage pipeline: (1) extract artifacts from PDF, (2) generate evidence by executing code in sandboxed Docker containers, (3) assess results via LLM evaluation across multiple dimensions. The agent containers communicate back to the Flask backend via HTTP (never direct DB access).

## Commands

### Run the app (Docker)
```bash
docker-compose up -d          # start
docker-compose logs -f        # view logs
```

### Run the app (local Python)
```bash
python app.py                 # requires ANTHROPIC_API_KEY in env
```

### Tests
```bash
pytest                        # run full suite (verbose by default via pytest.ini)
pytest tests/test_api.py -v   # single file
pytest tests/test_api.py::TestClassName::test_name -v  # single test
pytest -m unit                # only unit tests
pytest -m integration         # only integration tests
pytest tests/ --cov=.         # with coverage
```

Tests use a temp SQLite database per test (no real API key needed — conftest.py sets a dummy). No Docker or external services required for the test suite.

### Lint & format
```bash
black app.py agent.py tests/ --line-length=120
flake8 app.py agent.py tests/ --max-line-length=120
mypy app.py --ignore-missing-imports
```

### Build agent containers
```bash
docker build -t paper-reproducibility-agent:latest -f docker/Dockerfile.agent .
docker build -t paper-reproducibility-agent-ml:latest -f docker/Dockerfile.agent-ml .
```

## Architecture

- **Flask app** (`app.py`): Entry point, creates app via `create_app()` factory pattern
- **Blueprints** (`blueprints/`): Route handlers — `api.py` (agent communication), `jobs.py` (job CRUD + upload), `auth.py`, `admin.py`, `plugins.py`
- **Services** (`services/`): Business logic layer. `PipelineOrchestrator` is the main entry point that coordinates the three stages through `AnalysisService` → `DockerService` → `EvaluationService`. `EventDispatcher` is the central event hub persisting progress to the DB
- **Models** (`models/database.py`): Peewee ORM models — `User`, `Job`, `Event`, `PaperAnalysis`, `ExecutionDetails`, `Artifact`, `ChatSession`, `ChatMessage`, plus cache models
- **Repositories** (`repositories/`): Data access layer wrapping Peewee queries
- **LLM** (`llm/`): Provider abstraction with `factory.py` selecting between `AnthropicProvider` and `OllamaProvider` based on config
- **Agent** (`agent.py`): Runs inside Docker containers, communicates with backend via `/api/agent/*` endpoints
- **Schemas** (`schemas/`): Request/response validation schemas

## Key Patterns

- **Event-driven progress**: Pipeline stages emit events via `EventDispatcher.emit()` → persisted to `Event` table → frontend polls `/api/job/<id>/full` every 200ms
- **Three-layer caching**: Paper analysis (PDF hash), code execution (repo hash), evaluation (paper+code hash) — controlled by `ENABLE_CACHING` env var
- **Agent isolation**: Code execution happens in Docker containers with 2GB RAM / 2 CPU limits. Agent asks backend "what to do" via POST `/api/agent/think`, backend proxies to Claude
- **Auth**: Session-based, admin user auto-created on startup. Credentials configurable via `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`ADMIN_EMAIL` env vars. Username `admin` grants admin privileges

## Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API access |
| `ANTHROPIC_MODEL` / `CLAUDE_MODEL` | No | `claude-opus-4-1` | Model selection |
| `ENABLE_CACHING` | No | `false` | Enable three-layer cache |
| `DOCKER_NETWORK` | No | `''` | Docker network for agent containers |
| `DOCKER_BACKEND_URL` | No | `http://localhost:5000` | URL agents use to reach backend |
| `DATA_DIR` | No | `data` | Directory for database and uploads |
| `DATABASE_PATH` | No | `data/reproducibility.db` | SQLite database path |
| `ADMIN_USERNAME` | No | `admin` | Admin account username |
| `ADMIN_PASSWORD` | No | *(random)* | Admin password; re-applied on restart when set |
| `ADMIN_EMAIL` | No | `admin@example.com` | Admin account email |
