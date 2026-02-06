# Paper Reproducibility Checker 📄

Analyze scientific papers for reproducibility. Automatically extracts code artifacts, executes them in isolated Docker containers, and evaluates them against 15 reproducibility metrics.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key

### Setup
```bash
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

export ANTHROPIC_API_KEY="sk-ant-..."
docker-compose up

# Open http://localhost:5000
```

## Usage

### Web UI
Open http://localhost:5000 to upload papers and view results.

### Command Line
```bash
python scripts/repro-cli.py \
  -u http://localhost:5000 \
  -k <api_key> \
  -p paper.pdf \
  -o results.json
```

## How It Works

**Three-stage pipeline:**
1. **Paper Analysis** — Extract methodology, claims, datasets
2. **Code Execution** — Clone and run code in isolated containers
3. **Evaluation** — Compare paper claims vs execution results

Result: Detailed reproducibility report with 15-aspect scoring.

## Documentation

- **[Architecture](./docs/ARCHITECTURE.md)** — System design, database, caching
- **[API Reference](./docs/API.md)** — REST endpoints
- **[Development](./docs/DEVELOPMENT.md)** — Setup, configuration, workflow
- **[Testing](./docs/TESTING.md)** — Running tests

See `/docs` for full documentation.

