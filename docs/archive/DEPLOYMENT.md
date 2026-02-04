# Production Deployment

Guide for deploying to production environments.

## Pre-Deployment Checklist

### Security
- [ ] ANTHROPIC_API_KEY in environment variables (not code)
- [ ] Flask SECRET_KEY set (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] HTTPS/TLS configured on reverse proxy
- [ ] CORS properly configured (limit to your domain)
- [ ] Rate limiting enabled (Redis backend)
- [ ] Database password protected (if PostgreSQL)
- [ ] Regular security updates (`pip audit`, `docker image scan`)

### Infrastructure
- [ ] Reverse proxy (nginx/Traefik) configured
- [ ] SSL certificates valid (use Let's Encrypt)
- [ ] Database (PostgreSQL) deployed and tested
- [ ] Redis instance ready (for sessions, rate limiting)
- [ ] Monitoring/alerting set up
- [ ] Logging aggregation configured
- [ ] Backups automated

### Performance
- [ ] Gunicorn workers tuned (4-8 workers typical)
- [ ] Database connection pooling enabled
- [ ] Redis cache for frequent queries
- [ ] CDN for static files (optional)
- [ ] Load balancing for multiple workers

---

## Docker Compose Production Setup

### Configuration

Create `production.yml` override:

```yaml
version: '3.8'
services:
  app:
    build: .
    restart: always
    environment:
      FLASK_ENV: production
      FLASK_DEBUG: 0
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DATABASE_URL: postgresql://user:pass@db:5432/paper_repro
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    volumes:
      - uploads:/app/uploads
      - logs:/app/logs
    labels:
      - "com.example.version=0.3.0"
  
  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_DB: paper_repro
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
  
  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  uploads:
  logs:
  db_data:
  redis_data:
```

### Start Production

```bash
# Set environment variables
export ANTHROPIC_API_KEY="sk-ant-..."
export DB_PASSWORD="secure-password"

# Start with production config
docker-compose -f docker-compose.yml -f production.yml up -d

# Verify services
docker-compose ps
docker-compose logs -f app

# Check health
curl http://localhost:5000/health
```

---

## PostgreSQL Migration

Replace SQLite with PostgreSQL for production scale.

### Update Requirements

```bash
pip install psycopg2-binary SQLAlchemy
```

### Update app.py

```python
# Before
import sqlite3

# After
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Connect to PostgreSQL
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///reproducibility.db'))
SessionLocal = sessionmaker(bind=engine)
```

### Initialize Database

```bash
# Create tables
docker-compose exec app python -c "
from app import init_db
init_db()
"
```

---

## Reverse Proxy (nginx)

Expose application with HTTPS and path-based routing.

### nginx Configuration

```nginx
upstream paper_app {
    server localhost:5000;
    keepalive 32;
}

server {
    listen 80;
    server_name reproducibility.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name reproducibility.example.com;
    
    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/reproducibility.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reproducibility.example.com/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://paper_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
    }
    
    # Static files caching
    location ~* \.(js|css|png|jpg|svg)$ {
        proxy_pass http://paper_app;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Get SSL Certificate

```bash
sudo certbot certonly --standalone \
  -d reproducibility.example.com

# Or with webroot if nginx already serving
sudo certbot certonly --webroot \
  -w /var/www/html \
  -d reproducibility.example.com
```

---

## Gunicorn Configuration

Use Gunicorn for production WSGI server.

### Create `gunicorn.conf.py`

```python
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 2
worker_connections = 1000
timeout = 60
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Restart worker periodically
max_requests = 1000
max_requests_jitter = 50

# Graceful shutdown
graceful_timeout = 30

# Environment
raw_env = [
    "FLASK_ENV=production",
]
```

### Start with Gunicorn

```bash
gunicorn \
  --config gunicorn.conf.py \
  --env ANTHROPIC_API_KEY="sk-ant-..." \
  app:app
```

Or in Docker:

```dockerfile
# Update Dockerfile
FROM python:3.11

RUN pip install gunicorn

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
```

---

## Monitoring & Logging

### Health Check Endpoint

```python
@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.3.0"
    })
```

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Logging Aggregation

Use ELK (Elasticsearch, Logstash, Kibana) or Loki:

```python
import logging
from pythonjsonlogger import jsonlogger

# JSON logging for aggregation
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### Monitoring Metrics

Track:
- **Response time** - API latency
- **Error rate** - 4xx/5xx percentage
- **Queue depth** - Pending analysis jobs
- **Resource usage** - CPU, memory, disk
- **Database connections** - Pool usage
- **Agent execution time** - Per job timing

---

## Backup Strategy

### Database Backups

```bash
# PostgreSQL backup
PGPASSWORD=${DB_PASSWORD} pg_dump \
  -h localhost \
  -U postgres \
  paper_repro > backup_$(date +%Y%m%d).sql

# Restore
PGPASSWORD=${DB_PASSWORD} psql \
  -h localhost \
  -U postgres \
  paper_repro < backup_20260203.sql
```

### File Backups

```bash
# Backup uploads
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/

# S3 backup (using AWS CLI)
aws s3 cp uploads_backup_*.tar.gz s3://backup-bucket/
```

### Automated Backup Cron

```bash
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/backup.sh
```

---

## Scaling Strategies

### Horizontal Scaling (Multiple Workers)

```yaml
# Multiple app instances behind load balancer
services:
  app-1:
    build: .
    environment: ...
  
  app-2:
    build: .
    environment: ...
  
  app-3:
    build: .
    environment: ...
  
  nginx:
    image: nginx
    ports:
      - "80:80"
    depends_on:
      - app-1
      - app-2
      - app-3
```

### Shared Session Store

```python
# Use Redis for session storage
from flask_session import Session
from redis import Redis

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = Redis(host='redis', port=6379)
Session(app)
```

### Async Job Processing

```python
# Use Celery for long-running jobs
from celery import Celery

celery = Celery(app.name, broker='redis://localhost:6379')

@celery.task
def analyze_paper(job_id, pdf_path):
    # Long-running analysis
    pass
```

---

## Disaster Recovery

### RTO/RPO Targets
- **RTO (Recovery Time Objective):** 1 hour
- **RPO (Recovery Point Objective):** 15 minutes

### Failover Plan

1. **Detect failure** - Health check fails
2. **Alert team** - Monitoring system
3. **Failover** - Switch to backup database
4. **Restore** - Latest backup from S3
5. **Verify** - Test endpoint access

### Regular Testing

```bash
# Monthly disaster recovery drill
# 1. Restore database from backup to test environment
# 2. Verify all data present
# 3. Test application access
# 4. Document any issues
```

---

## Security Hardening

### SSL/TLS
- [x] Use TLS 1.2+
- [x] Strong ciphers (no RC4, MD5)
- [x] Certificate renewal automation

### Headers
- [x] HSTS (Strict-Transport-Security)
- [x] CSP (Content-Security-Policy)
- [x] X-Frame-Options (SAMEORIGIN)
- [x] X-Content-Type-Options (nosniff)

### Rate Limiting
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379"
)

@app.route('/upload')
@limiter.limit("5 per hour")
def upload_pdf():
    pass
```

### Authentication
- [ ] Implement API key authentication
- [ ] Add JWT token support
- [ ] Enable two-factor authentication
- [ ] Session timeout (30 minutes)

---

## Performance Tuning

### Database Connection Pooling

```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    os.getenv('DATABASE_URL'),
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

### Caching

```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379/0')
})

@app.route('/jobs')
@cache.cached(timeout=60)
def list_jobs():
    pass
```

### Query Optimization

- Index frequently queried columns (job_id, status, created_at)
- Use EXPLAIN PLAN to identify slow queries
- Archive old jobs to separate table

---

## Rollback Procedure

If deployment fails:

```bash
# Rollback to previous image
docker pull paper-reproducibility:0.2.0
docker tag paper-reproducibility:0.2.0 paper-reproducibility:latest
docker-compose up -d

# Or stop and restart previous container
docker-compose stop
docker-compose start
```

---

## Deployment Checklist (Day 1)

- [ ] Environment variables set
- [ ] SSL certificate installed
- [ ] Reverse proxy configured
- [ ] Database initialized
- [ ] Backups configured
- [ ] Monitoring active
- [ ] Health checks passing
- [ ] Load testing done (100 concurrent users)
- [ ] Team trained on procedures
- [ ] Documentation updated

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system overview.
