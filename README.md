# Paper Reproducibility Checker 📄

A production-ready web application that analyzes scientific papers for reproducibility by automatically extracting code artifacts, executing them in isolated Docker containers, and evaluating them against 15 reproducibility metrics.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key (`ANTHROPIC_API_KEY`)

### Setup

```bash
# Clone and run
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start
docker-compose up

# Open http://localhost:5000
```

## Overview

The system implements a **three-stage evaluation pipeline**:

1. **Paper Analysis** — Extract methodology, claims, and datasets from PDFs
2. **Code Execution** — Clone repos and execute code in Docker sandboxes
3. **Multi-Source Evaluation** — Compare paper claims vs code vs execution results

Result: Comprehensive reproducibility report scoring 15 key aspects.

## Features

✨ **v0.4.0**
- Multi-layer caching (3x speedup on repeated analyses)
- Citations extraction from papers
- Live progress timeline with 3-stage pipeline visualization
- Paper metadata (title, abstract) on detail page
- Configurable agent context limit
- Full reproducibility checklist (15 aspects, tier-based)
- Professional UI with dark mode support

## Documentation

- **[Setup & Deployment](./docs/PROJECT_SETUP.md)** — Installation, Docker, production deployment
- **[API Reference](./docs/API.md)** — Full API documentation and examples
- **[Architecture](./docs/ARCHITECTURE.md)** — Technical design, database schema, caching strategy
- **[Testing](./docs/TESTING.md)** — Running tests, test suite overview
- **[Troubleshooting](./docs/DEBUGGING.md)** — Common issues and solutions
- **[Development](./docs/DEVELOPMENT.md)** — Environment variables, local setup

## Performance

- Paper extraction: 5-10s
- Code execution: 2-5 min (repo-dependent)
- Evaluation: 10-15s
- **Total: ~3-5 min per paper**
- With caching: 1-2s on cache hit

## License

MIT License - see [LICENSE](./LICENSE)

## Support

- **Issues:** [GitHub Issues](https://github.com/kkirchheim/paper-reproducibility/issues)
- **Docs:** See `/docs` directory
- **Questions:** [GitHub Discussions](https://github.com/kkirchheim/paper-reproducibility/discussions)

---

**Status:** ✅ Production Ready | **Repository:** https://github.com/kkirchheim/paper-reproducibility
