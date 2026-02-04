# Setup & Deployment Guide

## Local Development

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- Anthropic API key

### Quick Start

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

### Local (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p uploads

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run Flask
python app.py
```

Visit `http://localhost:5000`

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | - | Anthropic API key (`sk-ant-...`) |
| `ANTHROPIC_MODEL` | No | `claude-haiku-4-5` | Claude model (use `claude-opus-4-1` for better quality) |
| `LLM_PROVIDER` | No | `anthropic` | LLM provider (e.g., `ollama` for local) |
| `AGENT_CONTEXT_LIMIT` | No | `10000` | Max characters of agent output history in prompt |
| `BACKEND_URL` | No | `http://localhost:5000` | Backend URL for agents |
| `FLASK_ENV` | No | `production` | Flask environment |
| `FLASK_DEBUG` | No | `0` | Enable debug mode |

## Docker Compose

### Start Services
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f app
```

### Stop Services
```bash
docker-compose down
```

### Full Reset (Delete Database)
```bash
docker-compose down -v
```

## Production Deployment

### Prerequisites
- Server with 4GB+ RAM
- Docker & Docker Compose
- Reverse proxy (nginx, Traefik)
- PostgreSQL database
- TLS/SSL certificates

### Checklist
1. **Replace SQLite** with PostgreSQL for multi-server deployments
2. **Configure reverse proxy** (nginx/Traefik) for HTTPS
3. **Set strong secret key** in Flask configuration
4. **Enable authentication** for sensitive operations
5. **Configure logging** aggregation (ELK, Loki)
6. **Set up monitoring** (Prometheus, Grafana)
7. **Schedule database backups** daily
8. **Enable rate limiting** on API endpoints
9. **Run security audit** (`pip audit`)
10. **Test disaster recovery** procedures

See [ARCHITECTURE.md](./ARCHITECTURE.md) for complete production checklist.

## Port Management

### Default Ports
- `5000` — Flask web application
- `6379` — Redis (optional, for scaling)

### Change Port
```bash
# Edit docker-compose.yml
# Change "5000:5000" to "5001:5000"

# Or use environment variable
docker-compose up -e FLASK_PORT=5001
```

### Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000

# Kill process
kill -9 <PID>
```

## Troubleshooting Setup

### Container Won't Start
```bash
# Check logs
docker-compose logs app

# Rebuild without cache
docker-compose build --no-cache app
docker-compose up
```

### API Key Not Working
```bash
# Verify format
echo $ANTHROPIC_API_KEY
# Should start with: sk-ant-

# Verify in container
docker-compose exec app echo $ANTHROPIC_API_KEY
```

### Out of Disk Space
```bash
# Clean up Docker
docker system prune -a

# Check disk usage
du -sh ~/.docker/
```

For more troubleshooting, see [DEBUGGING.md](./DEBUGGING.md).
