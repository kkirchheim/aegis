# Troubleshooting Guide

Solutions for common issues.

## Docker Issues

### Port 5000 Already in Use

**Error:**
```
docker: Error response from daemon: Ports are not available
```

**Solution:**
```bash
# Find process using port 5000
lsof -i :5000

# Kill it (if safe)
kill -9 <PID>

# Or use different port (edit docker-compose.yml)
ports:
  - "5001:5000"
```

### Docker Daemon Not Accessible

**Error:**
```
Cannot connect to Docker daemon
```

**Solution:**
```bash
# Start Docker daemon
sudo systemctl start docker

# Or add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker ps
```

### Insufficient Disk Space

**Error:**
```
no space left on device
```

**Solution:**
```bash
# Clean up Docker
docker system prune -a --volumes

# Check disk usage
df -h

# Remove old images
docker image prune -a
```

---

## API & Backend Issues

### 404 Job Not Found

**Error:**
```
{"error": "Job not found"}
```

**Cause:** Job ID doesn't exist or was deleted.

**Solution:**
```bash
# List all jobs
curl http://localhost:5000/jobs

# Use valid job_id from response
```

### CSRF Token Missing

**Error:**
```
CSRF token is missing
```

**Cause:** Form submitted without CSRF token.

**Solution:** The frontend automatically includes CSRF tokens. Check browser console for form submission errors.

### API Key Not Recognized

**Error:**
```
Invalid API key
```

**Solution:**
```bash
# Verify key format
echo $ANTHROPIC_API_KEY
# Should start with: sk-ant-

# If not set:
export ANTHROPIC_API_KEY="your-key-here"

# Restart Docker
docker-compose restart app
```

---

## Agent Execution Issues

### Agent Container Exits Immediately

**Error:**
```
paper-reproducibility exited with code 1
```

**Debug:**
```bash
# View agent logs
docker-compose logs paper-reproducibility | tail -50

# Look for import errors, missing env vars
```

**Common Causes:**
- Missing `ANTHROPIC_API_KEY`
- Missing `REPO_URL`
- Git clone failed (invalid URL)
- Python import error

**Solution:**
```bash
# Check environment
docker-compose exec app env | grep REPO_URL

# Verify git URL works
git clone https://github.com/user/repo /tmp/test
```

### Agent Stuck in Loop

**Symptom:** Agent keeps running same command repeatedly.

**Cause:** Output truncation (agent doesn't see completion messages).

**Check:** Output window in `app.py` line 556-558. Should be 2000+ chars.

**Solution:**
```bash
# View current setting
grep -n "last_output\[:2000" app.py

# If less than 2000, increase it
```

### Agent Can't Clone Repository

**Error in logs:**
```
fatal: could not read Username for 'https://github.com'
```

**Cause:** Private repo or network issue.

**Solution:**
```bash
# Test manually
docker run --rm python:3.11 git clone https://github.com/user/repo /tmp/test

# Check if repo is public
curl -I https://github.com/user/repo
```

---

## JSON Parsing Issues

### "Could Not Parse Claude Response"

**Error:**
```
✗ ALL PARSING METHODS FAILED!
Response text: I think the agent should...
```

**Cause:** Claude returned prose instead of JSON.

**Debug Steps:**

1. Check Claude response in logs:
```bash
docker-compose logs | grep "Claude Response"
```

2. Look for parsing attempts:
```
✓ Parsed JSON directly (Method 1)    # Success
✗ Direct JSON parsing failed: ...    # Failed
```

3. Four parsing methods tried (in order):
   - Method 1: Direct `json.loads()` - Plain JSON
   - Method 2: Extract from ` ```json ` - Markdown JSON block
   - Method 3: Extract from ` ``` ` - Plain code block
   - Method 4: Find substring - Partial JSON

**Solutions:**

If Method 1 fails → Claude returned malformed JSON:
```bash
# Check response for syntax errors
# May need to improve Claude prompt clarity
```

If all methods fail → Claude returned prose:
```bash
# Improve prompt (be more explicit)
# Add format reminders: "Return ONLY valid JSON"
# Check if token limit is too low
```

---

## Database Issues

### Database Locked

**Error:**
```
database is locked
```

**Cause:** SQLite can only handle one writer at a time.

**Solution:**
```bash
# Close any open connections
docker-compose restart app

# Or increase timeout
PRAGMA busy_timeout = 5000;
```

### Database Corrupted

**Error:**
```
database disk image is malformed
```

**Solution:**
```bash
# Backup (if recoverable)
cp reproducibility.db reproducibility.db.backup

# Delete and rebuild
rm reproducibility.db
docker-compose restart app
```

---

## Performance Issues

### Slow PDF Extraction

**Symptom:** Upload page hangs for large PDFs.

**Cause:** Large PDFs take time to extract.

**Solution:**
```bash
# Monitor progress
docker-compose logs -f | grep "Extracted"

# Increase timeout if needed
# Note: Max PDF size is 100MB (hard limit)
```

### High Memory Usage

**Symptom:** Docker container using excessive memory.

**Check:**
```bash
docker stats
```

**Solutions:**
```bash
# Reduce agent memory limit (in docker-compose.yml)
mem_limit: "1g"

# Or increase host memory available
```

### Slow Database Queries

**Symptom:** Page loads slow.

**Check:**
```bash
# View slow query log (if enabled)
sqlite3 reproducibility.db "PRAGMA query_only = ON;"

# Profile with timing
time sqlite3 reproducibility.db "SELECT COUNT(*) FROM jobs;"
```

---

## Network Issues

### Agent Can't Reach Backend

**Error in logs:**
```
Failed to report completion: connection refused
```

**Cause:** Backend URL incorrect or service not running.

**Debug:**
```bash
# Verify backend is running
docker-compose ps

# Check agent's backend URL (should be http://paper-reproducibility:5000)
docker-compose exec paper-reproducibility env | grep BACKEND_URL

# Test from agent container
docker-compose exec paper-reproducibility curl http://paper-reproducibility:5000/
```

### Frontend Can't Connect to Backend

**Symptom:** "Failed to load" in browser console.

**Cause:** Backend not running or wrong URL.

**Debug:**
```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs app

# Test manually
curl http://localhost:5000/jobs
```

---

## Browser Issues

### "CORS Error" in Console

**Error:**
```
Access to XMLHttpRequest blocked by CORS policy
```

**Cause:** Frontend and backend on different ports/domains.

**Solution:**
```bash
# For local development, should not occur
# If it does, backend may be on wrong URL

# Check frontend's backend URL in static/app.js
grep "localhost" static/app.js

# Should be: http://localhost:5000
```

### Event Stream Not Connecting

**Symptom:** Progress bar doesn't update in real-time.

**Debug:**
```bash
# Check Network tab in browser developer tools
# Look for GET /events/{job_id}
# Should show "text/event-stream" content type

# Or test manually
curl -N http://localhost:5000/events/abc-123
# Should start streaming events
```

---

## File & Permission Issues

### "Permission Denied" in Container

**Error:**
```
Permission denied while trying to connect to Docker daemon
```

**Cause:** User not in docker group or permission issue.

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Or run with sudo
sudo docker-compose up
```

### PDF File Not Found

**Error:**
```
File not found in uploads/
```

**Cause:** File was deleted or upload failed.

**Solution:**
```bash
# Check uploads directory
ls -la uploads/

# Recreate if needed
mkdir -p uploads

# Re-upload PDF
```

---

## Development & Testing Issues

### Tests Fail with "ModuleNotFoundError"

**Error:**
```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Or run inside Docker
docker-compose exec app pytest tests/ -v
```

### Import Error in Local Python

**Error:**
```
ModuleNotFoundError: No module named 'flask'
```

**Solution:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run Flask
python app.py
```

---

## Getting Help

### Check Logs First

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs app
docker-compose logs paper-reproducibility

# Filter
docker-compose logs | grep ERROR
docker-compose logs | grep -E "Failed|Exception|Error"

# Live view
docker-compose logs -f --tail=50
```

### Enable Debug Mode

```bash
# In .env file
FLASK_DEBUG=1
FLASK_ENV=development

# Restart
docker-compose restart app

# Logs will be more verbose
```

### Database Inspection

```bash
# Connect to SQLite
sqlite3 reproducibility.db

# Useful queries
.schema                              # View tables
SELECT COUNT(*) FROM jobs;          # Job count
SELECT * FROM jobs LIMIT 1;         # View a job
SELECT COUNT(*) FROM events WHERE job_id='abc';  # Events for job
.exit                               # Exit
```

### Network Debugging

```bash
# Inside Docker container
docker-compose exec app bash

# Test connectivity
curl -v http://paper-reproducibility:5000/
curl -v https://api.anthropic.com/  # Check internet

# Check DNS
nslookup google.com
```

---

## Common FAQ

**Q: Why is the agent running in Docker?**
A: Safety and reproducibility. Code runs in isolated sandbox with resource limits.

**Q: Can I access the database directly?**
A: Yes: `sqlite3 reproducibility.db`. But be careful with modifications.

**Q: How do I reset everything?**
A: `docker-compose down -v` (removes all volumes), then `docker-compose up`.

**Q: Can I use a different database?**
A: Yes (PostgreSQL recommended for production). Edit `app.py` database configuration.

**Q: What logs should I check?**
A: In order: Docker logs → Application logs → Database logs → Browser console.

See [ARCHITECTURE.md](./ARCHITECTURE.md) and [DEVELOPMENT.md](./DEVELOPMENT.md) for more details.
