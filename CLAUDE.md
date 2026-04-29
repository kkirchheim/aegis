# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Artifact Review — a Flask web app that analyzes academic papers for reproducibility. It runs a three-stage pipeline: (1) extract artifacts from PDF, (2) generate evidence by executing code in sandboxed Docker containers, (3) assess results via LLM evaluation across multiple dimensions. The agent containers communicate back to the Flask backend via HTTP (never direct DB access).

## Directory Structure

```
src/           # Application source (blueprints, services, models, repositories, schemas, llm, utils, app.py, config.py)
agent/         # Agent code + agent Dockerfiles (standalone, no imports from src/)
web/           # Frontend assets (static/, templates/)
tests/         # Test suite
docker/        # Main app Dockerfile
scripts/       # CLI tools
docs/          # Documentation
```

All imports use bare module names (e.g., `from models.database import X`). The `src/` directory is added to Python's module search path via `PYTHONPATH` (Docker) or `sys.path` (tests/scripts).

## Commands

### Run the app (Docker)
```bash
docker-compose up -d          # start
docker-compose logs -f        # view logs
```

### Run the app (local Python)
```bash
PYTHONPATH=src python src/app.py   # requires ANTHROPIC_API_KEY in env
```

### Tests
```bash
pytest                        # run full suite (verbose by default via pytest.ini)
pytest tests/test_api.py -v   # single file
pytest tests/test_api.py::TestClassName::test_name -v  # single test
pytest -m unit                # only unit tests
pytest -m integration         # only integration tests
pytest tests/ --cov=src       # with coverage
```

Tests use a temp SQLite database per test (no real API key needed — conftest.py sets a dummy). No Docker or external services required for the test suite.

### Lint & format
```bash
black src/ agent/ tests/ --line-length=120
flake8 src/ agent/ tests/ --max-line-length=120
mypy src/app.py --ignore-missing-imports
```

### Build agent containers
```bash
scripts/build_agent_images.sh
```

To rebuild without Docker layer cache:

```bash
scripts/build_agent_images.sh --no-cache
```

Equivalent individual commands:

```bash
docker build -t paper-reproducibility-agent:latest -f agent/Dockerfile .
docker build -t paper-reproducibility-agent-ml:latest -f agent/Dockerfile.ml .
docker build -t paper-reproducibility-agent-py27:latest -f agent/Dockerfile.py27 .
docker build -t paper-reproducibility-agent-py34:latest -f agent/Dockerfile.py34 .
docker build -t paper-reproducibility-agent-py36:latest -f agent/Dockerfile.py36 .
docker build -t paper-reproducibility-agent-octave:latest -f agent/Dockerfile.octave .
docker build -t paper-reproducibility-agent-matlab-official:latest -f agent/Dockerfile.matlab-official .
```

The official MATLAB image builds from a locally licensed MathWorks image named
`matlab-licensed-test:r2025b` by default. Override it with
`--build-arg MATLAB_BASE_IMAGE=<tag>` when using a different committed base.
Install additional MathWorks products with
`--build-arg MATLAB_PRODUCTS="Computer_Vision_Toolbox Statistics_and_Machine_Learning_Toolbox"`.

## Architecture

- **Flask app** (`src/app.py`): Entry point, creates app via `create_app()` factory pattern
- **Blueprints** (`src/blueprints/`): Route handlers — `api.py` (agent communication), `jobs.py` (job CRUD + upload), `auth.py`, `admin.py`, `plugins.py`
- **Services** (`src/services/`): Business logic layer. `PipelineOrchestrator` is the main entry point that coordinates the three stages through `AnalysisService` → `DockerService` → `EvaluationService`. `EventDispatcher` is the central event hub persisting progress to the DB
- **Models** (`src/models/database.py`): Peewee ORM models — `User`, `Job`, `Event`, `PaperAnalysis`, `ExecutionDetails`, `Artifact`, `ChatSession`, `ChatMessage`, plus cache models
- **Repositories** (`src/repositories/`): Data access layer wrapping Peewee queries
- **LLM** (`src/llm/`): Provider abstraction with `factory.py` selecting between `AnthropicProvider` and `OllamaProvider` based on config
- **Agent** (`agent/agent.py`): Runs inside Docker containers, communicates with backend via `/api/agent/*` endpoints
- **Schemas** (`src/schemas/`): Request/response validation schemas

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
