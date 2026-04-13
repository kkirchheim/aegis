# Artifact Review

Prototype implementation for *"Towards Supporting Software Artefact Review via LLMs"*. Generates structured evidence about software artifacts referenced in scientific papers through a three-stage pipeline: extract artifacts, generate evidence, and assess results.

> **Warning:** This is a research prototype intended for local use only. Do not deploy publicly. The application mounts the Docker socket into the container, which grants the container effective root access to the host. See [Security](#security) below.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key

### Setup
```bash
git clone https://github.com/kkirchheim/artifact-review.git
cd artifact-review

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
scripts/build_agent_images.sh
```

To rebuild without Docker layer cache:

```bash
scripts/build_agent_images.sh --no-cache
```

The script builds these images:

```bash
docker build -t paper-reproducibility-agent:latest -f agent/Dockerfile .
docker build -t paper-reproducibility-agent-ml:latest -f agent/Dockerfile.ml .
docker build -t paper-reproducibility-agent-py27:latest -f agent/Dockerfile.py27 .
docker build -t paper-reproducibility-agent-py34:latest -f agent/Dockerfile.py34 .
docker build -t paper-reproducibility-agent-py36:latest -f agent/Dockerfile.py36 .
docker build -t paper-reproducibility-agent-matlab:latest -f agent/Dockerfile.matlab .
docker build -t paper-reproducibility-agent-matlab-official:latest -f agent/Dockerfile.matlab-official .
```

The Python 2.7, Python 3.4, and Python 3.6 legacy images run the control agent
with modern Python 3, but repository commands default to the selected legacy Conda
environment with `pip`. They also configure the old Anaconda free channel so
legacy packages can be installed when a paper requires them. Select a legacy
Python image in the upload form for papers that require old Python or legacy
scientific Python versions.

The `MATLAB Official` image expects a local licensed MathWorks base image named
`matlab-licensed-test:r2025b`. Create it by signing in to the official image,
then committing that running container from another terminal:

```bash
docker run --rm -it mathworks/matlab:r2025b matlab -licmode onlinelicensing
docker commit <container_id> matlab-licensed-test:r2025b
docker build -t paper-reproducibility-agent-matlab-official:latest -f agent/Dockerfile.matlab-official .
```

To use a different licensed base image tag:

```bash
docker build \
  --build-arg MATLAB_BASE_IMAGE=my-matlab-licensed-base:r2025b \
  -t paper-reproducibility-agent-matlab-official:latest \
  -f agent/Dockerfile.matlab-official .
```

To install toolboxes into the official MATLAB agent image during build, pass
`MATLAB_PRODUCTS`. For example, to add Computer Vision Toolbox, Statistics and
Machine Learning Toolbox, and Symbolic Math Toolbox:

```bash
docker build \
  --build-arg MATLAB_PRODUCTS="Computer_Vision_Toolbox Statistics_and_Machine_Learning_Toolbox Symbolic_Math_Toolbox" \
  -t paper-reproducibility-agent-matlab-official:latest \
  -f agent/Dockerfile.matlab-official .
```

The image includes MathWorks Package Manager as `mpm`. MATLAB commands are
wrapped so `matlab -batch "..."` automatically uses online licensing mode.

After changing an agent Dockerfile, rebuild the matching image before starting a
new job so Docker does not reuse an older local image.

## Security

This application requires the Docker socket (`/var/run/docker.sock`) to be mounted so it can spawn agent containers. This effectively gives the application root-level access to the host system. Additionally, the agent containers clone and execute arbitrary code from repositories referenced in uploaded papers.

**Do not expose this application to the public internet.** It is designed for local or trusted-network use only.

## Documentation

- **[Architecture](./docs/ARCHITECTURE.md)** — System design, database, caching
- **[API Reference](./docs/API.md)** — REST endpoints
- **[Development](./docs/DEVELOPMENT.md)** — Setup, configuration, workflow
- **[Testing](./docs/TESTING.md)** — Running tests
