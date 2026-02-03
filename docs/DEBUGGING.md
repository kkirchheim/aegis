# Debugging Guide

Quick troubleshooting for common issues.

## Quick Diagnostics

### Service Status
```bash
docker-compose ps
# All services should show "Up"
```

### Check Logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs app
docker-compose logs paper-reproducibility

# Live view
docker-compose logs -f --tail=50
```

### Enable Debug Mode
```bash
# In .env
FLASK_DEBUG=1
FLASK_ENV=development

# Restart
docker-compose restart app
```

## Common Issues

### Port 5000 Already in Use
```bash
lsof -i :5000
kill -9 <PID>

# Or use different port in docker-compose.yml
```

### Docker Daemon Not Accessible
```bash
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
```

### API Key Not Working
```bash
# Verify
echo $ANTHROPIC_API_KEY
# Should start with: sk-ant-

# Restart container
docker-compose restart app
```

### Job Not Found
```bash
# List all jobs
curl http://localhost:5000/jobs

# Use valid job_id
```

### Database Locked
```bash
docker-compose restart app
```

### Agent Stuck in Loop
Agent sees command output but doesn't advance. Increase `AGENT_CONTEXT_LIMIT` in `.env`.

### Tests Fail with "ModuleNotFoundError"
```bash
# Conftest should set path, verify:
cat tests/conftest.py

# Or run in Docker:
docker-compose exec app pytest tests/ -v
```

## Detailed Troubleshooting

For comprehensive troubleshooting, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) which covers:
- Docker issues (disk space, permissions)
- API & backend issues
- Agent execution problems
- JSON parsing failures
- Database issues
- Performance optimization
- Network debugging
- Browser console issues

## Database Inspection

```bash
# Open SQLite directly
sqlite3 reproducibility.db

# Useful queries
.schema                           # View all tables
SELECT COUNT(*) FROM jobs;        # Count jobs
SELECT * FROM jobs LIMIT 1;       # View a job
.exit
```

## Check Service Connectivity

```bash
# From app container
docker-compose exec app curl http://paper-reproducibility:5000/

# From agent
docker-compose exec paper-reproducibility curl http://paper-reproducibility:5000/
```

## Reset Everything

```bash
# Stop and remove all (keeps code)
docker-compose down

# Remove database too
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up
```

---

See [PROJECT_SETUP.md](./PROJECT_SETUP.md) for setup issues and [TESTING.md](./TESTING.md) for test failures.
