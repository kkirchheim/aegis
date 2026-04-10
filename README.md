# Artifact Review

Prototype implementation for *"Towards Supporting Software Artefact Review via LLMs"*. Generates structured evidence about software artifacts referenced in scientific papers through a three-stage pipeline: extract artifacts, generate evidence, and assess results.

> **Warning:** This is a research prototype intended for local use only. Do not deploy publicly. The application mounts the Docker socket into the container, which grants the container effective root access to the host. See [Security](#security) below.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key

### Setup
```bash
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY

docker-compose up -d
# Open http://localhost:5000
```

Default admin credentials are `admin` / `changeme` (configurable via `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`). If `ADMIN_PASSWORD` is unset, a random password is generated and printed to the logs on startup.

### Local Development (without Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY

PYTHONPATH=src python src/app.py
```

## Usage

### Web UI
Open http://localhost:5000 to upload papers and view results.

### CLI
```bash
python scripts/repro-cli.py \
  -u http://localhost:5000 \
  -k <api_key> \
  -p paper.pdf \
  -o results.json
```

## How It Works

1. **Extract** — Parse the PDF, identify software artifacts, and extract metadata
2. **Generate Evidence** — Run three types of evidence generators against extracted artifacts:
   - *Deterministic* — execution checks (scripts run inside Docker containers)
   - *Semantic* — LLM-based evaluation plugins
   - *Interactive* — agentic exploration of repositories in sandboxed containers
3. **Assess** — Aggregate evidence into a structured review context

## Project Structure

```
src/           # Application source (Flask app, services, models, blueprints)
agent/         # Agent code + agent Dockerfiles
web/           # Frontend assets (static/, templates/)
tests/         # Test suite
docker/        # Main app Dockerfile
scripts/       # CLI tools
docs/          # Documentation
```

## Agent Containers

Code execution happens inside isolated Docker containers, built automatically on first use. To build manually:

```bash
docker build -t paper-reproducibility-agent:latest -f agent/Dockerfile .
docker build -t paper-reproducibility-agent-ml:latest -f agent/Dockerfile.ml .
```

## Security

This application requires the Docker socket (`/var/run/docker.sock`) to be mounted so it can spawn agent containers. This effectively gives the application root-level access to the host system. Additionally, the agent containers clone and execute arbitrary code from repositories referenced in uploaded papers.

**Do not expose this application to the public internet.** It is designed for local or trusted-network use only.

## Documentation

- **[Architecture](./docs/ARCHITECTURE.md)** — System design, database, caching
- **[API Reference](./docs/API.md)** — REST endpoints
- **[Development](./docs/DEVELOPMENT.md)** — Setup, configuration, workflow
- **[Testing](./docs/TESTING.md)** — Running tests
