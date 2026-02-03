# Paper Reproducibility Checker 📄

A web application that analyzes scientific papers for reproducibility by automatically extracting code artifacts and executing them in isolated Docker containers with an LLM agent.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Python 3.10+ (for local development)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/konstantin/paper-reproducibility.git
   cd paper-reproducibility
   ```

2. **Set environment variables**
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up
   ```

4. **Open in browser**
   ```
   http://localhost:5000
   ```

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Create uploads directory
mkdir -p uploads logs

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run Flask app
python app.py
```

Then visit `http://localhost:5000`

## Usage

1. **Upload a PDF** - Click to upload a scientific paper (max 100MB)
2. **Watch Analysis** - See real-time progress as the system:
   - Extracts text from PDF
   - Analyzes with Claude to find code artifacts
   - Identifies reproducibility aspects
3. **View Report** - Get a reproducibility report with:
   - Code artifacts found (yes/no)
   - Reproducibility aspects (docs, hyperparams, implementation)
   - Execution status

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical design.

### High-Level Flow

```
PDF Upload
    ↓
Extract Text + Claude Parsing
    ↓
Find Code Artifacts
    ↓
For Each Artifact:
  - Spawn Docker container with LLM agent
  - Agent clones repo, reads README
  - Agent calls backend API to ask Claude what to do
  - Claude returns action: read_file, run_command, done
  - Agent executes, loops until done/error
    ↓
Aggregate Results → Report
    ↓
Display to User (real-time via SSE)
```

## API Reference

See [API.md](./API.md) for complete API documentation.

### Key Endpoints

- `POST /upload` - Upload PDF for analysis
- `GET /events/<job_id>` - Stream analysis progress (SSE)
- `GET /job/<job_id>` - Get job status and report
- `GET /jobs` - List all jobs
- `POST /api/agent/think` - Agent asks Claude what to do
- `POST /api/agent/log` - Agent logs progress

## Project Structure

```
paper-reproducibility/
├── app.py                  # Flask backend
├── agent.py               # LLM agent (runs in container)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image
├── docker-compose.yml     # Multi-container setup
├── reproducibility.db     # SQLite database
├── templates/
│   └── index.html        # Frontend
├── static/
│   ├── style.css         # Styling
│   └── app.js            # JavaScript
├── uploads/              # PDF storage
├── logs/                 # Application logs
├── docs/
│   ├── ARCHITECTURE.md   # Technical design
│   └── API.md            # API documentation
└── README.md             # This file
```

## Features

### Phase 1 (Current MVP)
- ✅ PDF upload and text extraction
- ✅ Claude-powered artifact detection
- ✅ Real-time progress via SSE
- ✅ Basic reproducibility scoring
- ✅ Job history

### Phase 2 (Planned)
- [ ] Docker agent execution (run code in containers)
- [ ] Intelligent agent loop (try fixes on errors)
- [ ] Execution output capture
- [ ] Result matching against paper claims

### Phase 3 (Future)
- [ ] Custom reproducibility checks via prompt
- [ ] Multi-paper analysis
- [ ] Advanced reporting (charts, trends)
- [ ] User accounts and authentication

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `FLASK_ENV` | No | `production` | Flask environment |
| `FLASK_DEBUG` | No | `0` | Enable debug mode |

## Security

- All PDFs stored in `uploads/` directory with UUID names
- API keys stored in environment variables (never in code)
- Docker containers run with resource limits (2GB RAM, 2 CPU)
- Network isolation for sandboxed code execution
- Agent never receives API key directly (calls backend instead)

## Troubleshooting

### Port 5000 already in use
```bash
# Use different port
docker-compose exec -e FLASK_PORT=5001 app python app.py
```

### API key not recognized
```bash
# Verify key format
echo $ANTHROPIC_API_KEY

# Should start with: sk-ant-
```

### Docker daemon not accessible
```bash
# Check Docker socket
ls -la /var/run/docker.sock

# May need to run with sudo or add user to docker group
sudo usermod -aG docker $USER
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Style
```bash
black app.py agent.py
flake8 app.py agent.py
```

### Database Schema
```bash
sqlite3 reproducibility.db ".schema"
```

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests
4. Submit pull request

## License

MIT License - see LICENSE file

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check [FAQ.md](./docs/FAQ.md)
- See [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)

## Next Steps

1. ✅ Phase 1: PDF parsing + artifact detection (complete)
2. ⏳ Phase 2: Docker agent execution (in progress)
3. ⏳ Phase 3: Advanced reproducibility checks
4. ⏳ Phase 4: Production deployment

---

**Status:** MVP Phase 1  
**Last Updated:** February 3, 2026  
**Maintainer:** @konstantin
