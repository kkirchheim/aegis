# Paper Reproducibility Checker 📄

A production-ready web application that analyzes scientific papers for reproducibility by automatically extracting code artifacts, executing them in isolated Docker containers, and evaluating them against 15 scientifically-backed reproducibility metrics.

## Overview

The Paper Reproducibility Checker implements a **three-stage evaluation pipeline**:

1. **Paper Analysis** - Claude extracts methodology, claims, and datasets from PDFs
2. **Code Execution** - Docker agent clones repos and executes code in sandboxes
3. **Multi-Source Evaluation** - Claude compares paper claims vs code vs execution results

Result: A comprehensive reproducibility report with 15 aspects ranked by importance.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key (`ANTHROPIC_API_KEY`)
- 2GB RAM minimum per agent container

### Setup

```bash
# Clone repository
git clone https://github.com/kkirchheim/paper-reproducibility.git
cd paper-reproducibility

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start with Docker Compose
docker-compose up

# Open browser
open http://localhost:5000
```

Done! No additional setup needed.

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Create directories
mkdir -p uploads

# Run Flask
python app.py
```

Visit `http://localhost:5000`

## Features

### 🎯 15 Reproducibility Aspects

#### Tier 1: CRITICAL (Must Have)
- **Dependencies Pinned** - Exact versions (==) vs ranges (>=)?
- **Results Reproducible** - Execution matches paper claims? (±2% tolerance)
- **Hyperparameters Documented** - Values documented AND correct?
- **Dataset Available** - Data public or easy to obtain?
- **Environment Documented** - Python version, OS specified?

#### Tier 2: HIGH VALUE (Recommended)
- **Test Suite Present** - Tests included?
- **Config File Present** - Hyperparameters externalized?
- **Documentation Quality** - README, comments, docstrings?
- **Randomness Controlled** - Random seeds set?

#### Tier 3: NICE-TO-HAVE (Optional)
- **License Specified** - Legal clarity?
- **Continuous Integration** - CI/CD configured?
- **Data Versioning** - Dataset version tracked?
- **Computational Requirements** - Time/memory documented?
- **Output Format Documented** - Output meaning clear?
- **Python Version Compatibility** - Multiple versions tested?

### 🏗️ Three-Stage Pipeline

```
┌──────────────────────────┐
│ 1. PAPER ANALYSIS        │
│ - Extract text, claims   │
│ - Identify datasets      │
│ - Find dependencies      │
└──────────────────────────┘
           ↓
┌──────────────────────────┐
│ 2. CODE EXECUTION        │
│ - Clone repository       │
│ - Discover files         │
│ - Detect test suite      │
│ - Run main script        │
│ - Capture output         │
└──────────────────────────┘
           ↓
┌──────────────────────────┐
│ 3. MULTI-SOURCE EVAL     │
│ - Compare paper vs code  │
│ - Check vs execution     │
│ - Score 15 aspects       │
│ - Generate report        │
└──────────────────────────┘
           ↓
┌──────────────────────────┐
│ REPRODUCIBILITY REPORT   │
│ - Checklist (tier-based) │
│ - Evidence from all 3    │
│ - Professional UI        │
└──────────────────────────┘
```

### 🎨 Professional UI

- **Tailwind CSS + DaisyUI** - Modern, clean scientific aesthetic
- **Dark Mode** - Toggle with localStorage persistence
- **Mobile Responsive** - Works on all screen sizes
- **Real-time Progress** - SSE stream of analysis events
- **Collapsible Evidence** - Multi-source evidence for each aspect
- **Status Badges** - Color-coded pass/partial/fail indicators

### 🔒 Security & Sandboxing

- **Docker Isolation** - Code runs in sandboxed containers (2GB RAM, 2 CPU cores)
- **Timeout Protection** - 300s timeout per command execution
- **Path Traversal Prevention** - No directory escape attacks
- **Auto-Cleanup** - Containers removed after execution
- **API Key Security** - Keys in environment variables only
- **No Direct Host Access** - Agent can't access host filesystem

## Usage

### Uploading a Paper

1. Click **Upload Paper** section
2. Select PDF file (max 100MB)
3. Click **Analyze Paper**

### View Progress

- Live log shows each analysis step
- Progress bar updates in real-time
- Agent status updates as it runs

### Review Report

Click on any job in **Previous Analyses** to view:
- Reproducibility checklist (grouped by tier)
- Artifact details (GitHub repos, datasets)
- Execution log with timestamps
- Collapsible evidence sections
- Dark mode toggle

## API Reference

### Upload & Status

```bash
# Upload PDF
curl -X POST -F "pdf=@paper.pdf" http://localhost:5000/upload

# Stream events (SSE)
curl http://localhost:5000/events/{job_id}

# Get job status
curl http://localhost:5000/job/{job_id}

# List all jobs
curl http://localhost:5000/jobs
```

### Agent API

```bash
# Agent asks what to do (internal)
curl -X POST -H "Content-Type: application/json" \
  -d '{"job_id": "...", "repo_state": {...}}' \
  http://localhost:5000/api/agent/think

# Agent logs progress (internal)
curl -X POST -H "Content-Type: application/json" \
  -d '{"job_id": "...", "message": "..."}' \
  http://localhost:5000/api/agent/log

# Agent submits execution details (internal)
curl -X POST -H "Content-Type: application/json" \
  -d '{"job_id": "...", "commands_run": "...", ...}' \
  http://localhost:5000/api/agent/execution

# Agent reports completion (internal)
curl -X POST -H "Content-Type: application/json" \
  -d '{"job_id": "...", "success": true, "message": "..."}' \
  http://localhost:5000/api/agent/complete
```

See [API.md](./API.md) for complete documentation.

## Project Structure

```
paper-reproducibility/
├── app.py                    # Flask backend (1500+ lines)
├── agent.py                  # Docker agent (600+ lines)
├── requirements.txt          # Python dependencies
├── Dockerfile                # Flask container
├── Dockerfile.agent          # Agent sandbox container
├── docker-compose.yml        # Multi-container orchestration
├── reproducibility.db        # SQLite database (auto-created)
├── templates/
│   ├── index.html           # Home page (Tailwind + DaisyUI)
│   └── detail.html          # Report page (Tailwind + DaisyUI)
├── static/
│   ├── app.js               # Home page logic
│   ├── detail.js            # Report page logic
│   └── style.css            # Minimal custom styles
├── uploads/                 # PDF storage (ephemeral)
├── tests/
│   ├── test_agent_api.py   # Test suite (11 tests)
│   └── README.md            # Testing guide
├── docs/
│   ├── ARCHITECTURE.md      # Technical design
│   ├── API.md               # API reference
│   ├── TESTING.md           # Testing documentation
│   ├── DEBUGGING.md         # Troubleshooting
│   └── PROJECT_SETUP.md     # Setup guide
└── README.md                # This file
```

## Database Schema

### Tables
- `jobs` - Job metadata, status, reports
- `artifacts` - Code artifacts (repos, datasets)
- `events` - Real-time analysis events
- `paper_analysis` - Extracted paper claims
- `execution_details` - Agent execution logs
- `aspect_evaluations` - Reproducibility scores

Auto-created on first run. See schema in `app.py:init_db()`.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | - | Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-opus-4-1` | Claude model to use |
| `BACKEND_URL` | No | `http://localhost:5000` | Backend URL for agents |
| `FLASK_ENV` | No | `production` | Flask environment |
| `FLASK_DEBUG` | No | `0` | Enable debug mode |

## Deployment

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Full reset
docker-compose down -v  # Deletes database
```

### Production Considerations

- Replace SQLite with PostgreSQL for multiple servers
- Use nginx/Traefik for reverse proxy + HTTPS
- Set up monitoring (Prometheus, Grafana)
- Configure logging aggregation (ELK, Loki)
- Enable authentication/authorization
- Set up database backups

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for production checklist.

## Testing

### Run Test Suite

```bash
# All tests
docker-compose exec app pytest tests/test_agent_api.py -v

# Specific test
docker-compose exec app pytest tests/test_agent_api.py::TestStateValidation -v

# With coverage
docker-compose exec app pytest tests/test_agent_api.py --cov=app
```

### Tests Included
- None value edge cases (11 tests)
- State validation
- Error handling
- JSON parsing
- Agent API responses

See [tests/README.md](./tests/README.md) for details.

## Troubleshooting

### Port 5000 Already in Use
```bash
# Find process
lsof -i :5000

# Use different port
docker-compose -f docker-compose.yml up -e FLASK_PORT=5001
```

### API Key Not Working
```bash
# Verify format
echo $ANTHROPIC_API_KEY
# Should start with: sk-ant-

# Verify it's set
docker-compose exec app echo $ANTHROPIC_API_KEY
```

### Container Won't Start
```bash
# Check logs
docker-compose logs app

# Rebuild image
docker-compose build --no-cache app
docker-compose up
```

### Agent Container Errors
```bash
# View agent logs
docker-compose logs paper-reproducibility-agent

# Check Docker permissions
docker ps

# Verify network
docker network ls | grep workspace_traefik
```

See [DEBUGGING.md](./docs/DEBUGGING.md) for more troubleshooting.

## Features Implemented

### Phase 1: Complete ✅
- PDF text extraction
- Claude-powered artifact detection
- Real-time progress updates (SSE)
- Job history and persistence

### Phase 2: Complete ✅
- Docker agent execution
- Code artifact analysis
- Dependency tracking
- Execution output capture
- Error handling and recovery

### Phase 3: Complete ✅
- **15 reproducibility aspects** (tier-based)
- **Multi-source evaluation** (paper vs code vs execution)
- **Professional UI** (Tailwind + DaisyUI)
- **Dark mode support**
- **Mobile responsive design**
- **Comprehensive test suite**
- **Detailed documentation**

### Future Ideas
- [ ] Reproducibility scoring (0-100%)
- [ ] Comparison reports (multiple papers)
- [ ] PDF export functionality
- [ ] Team collaboration features
- [ ] Custom evaluation rules
- [ ] Multi-language support
- [ ] CI/CD integration

## Performance

- **Paper extraction:** 5-10 seconds
- **Code execution:** 2-5 minutes (varies by repo)
- **Evaluation:** 10-15 seconds
- **Total:** ~3-5 minutes per paper
- **Container startup:** 3-5 seconds
- **Memory:** ~500MB per agent container
- **Throughput:** 1 paper per 5 minutes (with single agent)

## Architecture

The system uses:
- **Backend:** Flask (Python)
- **Frontend:** Tailwind CSS + DaisyUI (HTML/JS)
- **Execution:** Docker containers (sandboxed)
- **Database:** SQLite
- **API:** Anthropic Claude
- **Real-time:** Server-Sent Events (SSE)

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for detailed technical design.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and test (`pytest tests/`)
4. Commit with clear messages (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

MIT License - see [LICENSE](./LICENSE) file

## Citation

If you use this tool in research, please cite:

```bibtex
@software{paper_reproducibility_2026,
  title={Paper Reproducibility Checker},
  author={Konstantin},
  year={2026},
  url={https://github.com/kkirchheim/paper-reproducibility},
  note={Docker-based reproducibility assessment for scientific papers}
}
```

## Support & Contact

- **Issues:** GitHub Issues
- **Questions:** GitHub Discussions
- **Docs:** See `/docs` directory
- **Troubleshooting:** See [DEBUGGING.md](./docs/DEBUGGING.md)

## Changelog

### v0.3.0 (Feb 3, 2026)
- Added 15 reproducibility aspects (tier-based)
- Implemented multi-source evaluation (paper + code + execution)
- Redesigned UI with Tailwind CSS + DaisyUI
- Added dark mode support
- Enhanced documentation

### v0.2.0 (Feb 1, 2026)
- Implemented Docker agent execution
- Added execution details capture
- Fixed container cleanup race condition
- Added comprehensive test suite

### v0.1.0 (Jan 31, 2026)
- Initial release
- PDF parsing and artifact detection
- Real-time progress updates

---

**Status:** ✅ Production Ready  
**Last Updated:** February 3, 2026  
**Maintainer:** @kkirchheim  
**Repository:** https://github.com/kkirchheim/paper-reproducibility
