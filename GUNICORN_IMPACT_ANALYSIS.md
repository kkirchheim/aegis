# Gunicorn Multi-Processing Impact Analysis

## Overview
Switching from Flask dev server (single process) to **Gunicorn with 4+ worker processes** would require careful refactoring. Here's what would break and how to fix it.

---

## 🔴 **CRITICAL ISSUES**

### 1. **Global Dispatcher & Orchestrator Instances**
**Location:** `blueprints/jobs.py:15-16`
```python
_dispatcher = EventDispatcher()
_orchestrator = PipelineOrchestrator(dispatcher=_dispatcher)
```

**Problem:** Each Gunicorn worker gets its own copy of these singletons. They don't share state.

**Current Impact (polling):** 
- ✅ **MEDIUM RISK** - Since we switched to polling (`/api/job/{id}/full`), not SSE, events are read from DB
- But EventDispatcher still maintains in-memory event history for logging/debugging
- In multi-process, each worker only sees its own events

**Solution:**
- Option A: Move event state to Redis (distributed)
- Option B: Keep polling from DB only (current approach works fine)
- Option C: Use Celery + message broker instead of threading

---

### 2. **SQLite Database**
**Location:** `models/database.py`
```python
db = SqliteDatabase(Config.DATABASE)
```

**Problem:** SQLite has limited concurrency. With Gunicorn:
- Multiple workers = concurrent writes = **database lock timeouts**
- "database is locked" errors under moderate load
- No connection pooling

**Severity:** 🔴 **CRITICAL**

**Solution:**
- Must migrate to **PostgreSQL**
- Add connection pooling (pgBouncer)
- Peewee ORM already supports PostgreSQL, just config change

---

### 3. **Threading.Lock in EventDispatcher**
**Location:** `services/event_dispatcher.py:20-22`
```python
def __init__(self, event_queues=None, event_queues_lock: Lock = None):
    self.event_queues_lock = event_queues_lock or Lock()
```

**Problem:** Lock is thread-safe but **not process-safe**. With multiprocessing:
- Each worker process has its own Lock instance
- Processes can't synchronize on same lock
- Race conditions on shared data across processes

**Severity:** 🔴 **CRITICAL** if using SSE, **MEDIUM** if polling only

**Solution:**
- Replace threading.Lock with Redis lock or file-based lock
- Or eliminate need for lock by using DB-backed state

---

### 4. **Background Threading in Flask Routes**
**Location:** `blueprints/api.py:1267-1275` (PDF upload) and chat responses

```python
thread = threading.Thread(
    target=analyze_paper_background,
    args=(job_id, str(pdf_path), config, llm_provider),
    daemon=True
)
thread.start()
```

**Problem:** 
- Thread starts in **one worker process only**
- If that worker crashes, background job dies
- No job persistence or retry logic

**Severity:** 🟠 **HIGH**

**Solution:**
- Replace with Celery (or similar task queue)
- Jobs persisted to Redis/RabbitMQ
- Can retry, track status, distribute across workers

---

## 🟠 **HIGH-RISK ISSUES**

### 5. **Flask g Object for API Key Auth**
**Location:** `utils/decorators.py:70-72`
```python
g.user_id = user_id  # Stored in Flask g (request-local)
```

**Problem:** Flask `g` is thread-local but **not process-local**. 
- Each request in same worker thread uses same g
- Different worker process = different g
- **Actually this is FINE** - Flask creates new g per request anyway

**Severity:** 🟢 **GREEN** (no issue, Flask handles this)

---

### 6. **In-Memory Event History**
**Location:** `services/event_dispatcher.py` holds events in memory

**Problem:**
- Events from worker A not visible to worker B
- Client requests go to different workers (round-robin) → missing events

**Severity:** 🟠 **HIGH** if using SSE, **LOW** if using polling

**Current State:** We're using polling ✅ - **reads from DB, not memory cache**

---

### 7. **Environment Variables & Config**
**Location:** `config.py` reads from `os.environ`

**Problem:** Each process inherits parent env, but some libraries cache values
- Should be fine with standard Gunicorn setup
- But verify SECRET_KEY and sensitive values are same across workers

**Severity:** 🟢 **LOW** - not an issue with proper setup

---

## 🟡 **MEDIUM-RISK ISSUES**

### 8. **Docker Container Spawning**
**Location:** `services/docker_service.py` spawns containers for code execution

**Problem:**
- Each Gunicorn worker can spawn containers
- Multiple workers = multiple containers for same job
- "database is locked" when multiple containers write results

**Severity:** 🟡 **MEDIUM**

**Solution:**
- Lock job during execution (set `in_progress` flag)
- Queuing system ensures only one worker executes per job
- Move to Celery solves this

---

### 9. **Session Management**
**Location:** Flask session handling

**Problem:**
- If using in-memory sessions: lost between workers
- With cookie-based sessions: works fine (data in cookie, signed)

**Severity:** 🟡 **MEDIUM** - Current setup uses **server-side session** (peewee-session)

**Solution:**
- Switch to Redis-backed sessions
- Or use JWT tokens instead of sessions
- Or use database-backed sessions (already using Peewee)

**Current State:** Check if sessions are persisted to DB ✅ (likely fine)

---

### 10. **Polling Race Condition**
**Location:** `/api/job/{id}/full` polling endpoint

**Problem:**
- Client calls GET from different worker each request
- Job updates happen in different worker
- **Actually fine** - all workers read same DB ✅

**Severity:** 🟢 **GREEN** - no issue with DB-backed state

---

## ✅ **NO ISSUE - ALREADY SAFE**

### Good News:
- ✅ **Polling Architecture** - Reads from persistent DB, not in-memory cache
- ✅ **Stateless API** - No session affinity needed
- ✅ **Peewee ORM** - Handles connections properly
- ✅ **Flask g object** - Request-scoped, safe per-worker
- ✅ **Static files** - Nginx/reverse proxy will serve these

---

## 📋 **Migration Checklist to Gunicorn**

### Phase 1: **Database** (Required first)
- [ ] Set up PostgreSQL
- [ ] Update `Config.DATABASE` to PostgreSQL connection string
- [ ] Add connection pooling (pgBouncer or Peewee pool)
- [ ] Migrate SQLite data to PostgreSQL
- [ ] Test with 4+ workers under load

### Phase 2: **Background Jobs** (Required if using threads)
- [ ] Install Celery + Redis
- [ ] Replace `threading.Thread` with Celery tasks
- [ ] Update `analyze_paper_background()` to async task
- [ ] Update chat response generation to async task
- [ ] Test job queuing with multiple workers

### Phase 3: **Sessions** (if not already DB-backed)
- [ ] Verify sessions are in database (not in-memory)
- [ ] Or switch to Redis-backed sessions
- [ ] Test session persistence across worker restarts

### Phase 4: **Event Dispatcher** (Optional if not using SSE)
- [ ] If SSE still used: move to Redis Pub/Sub
- [ ] If polling only: keep as-is (reads from DB)
- [ ] Remove threading.Lock, use DB-backed locking

### Phase 5: **Docker Execution Locking** (Required)
- [ ] Add job locking mechanism (DB flag or Redis)
- [ ] Ensure only one worker executes per job
- [ ] Queue jobs with Celery if multiple pending

### Phase 6: **Configuration**
- [ ] Create `gunicorn.conf.py` with:
  - `workers = 4` (start with num_cpus)
  - `worker_class = "sync"` (or "gthread" for threads)
  - `max_requests = 1000` (restart workers periodically)
  - `timeout = 120` (long-running analysis jobs)
- [ ] Update Docker Compose or Kubernetes manifests
- [ ] Set up Nginx reverse proxy with load balancing

### Phase 7: **Testing**
- [ ] Load test with 10+ concurrent users
- [ ] Verify no "database is locked" errors
- [ ] Check job execution doesn't duplicate
- [ ] Monitor worker memory/CPU usage
- [ ] Test graceful shutdown (in-flight jobs complete)

---

## **Recommended Approach** 🎯

**Option A: Minimal (Simple, works with polling)**
1. Migrate to PostgreSQL
2. Keep Flask dev server OR use Gunicorn with `worker_class="gthread"` (threads in one process)
3. No changes needed to code
4. **Pros:** Easiest, quick win
5. **Cons:** Still single-process bottleneck, threads share CPU (GIL)

**Option B: Proper (Best for production)**
1. Migrate to PostgreSQL
2. Add Celery + Redis for background jobs
3. Use Gunicorn with 4-8 sync workers
4. Add Redis-backed sessions (optional, if needed)
5. Implement DB-backed job locking
6. **Pros:** Proper multi-process, scalable, resilient
7. **Cons:** More complex, more infrastructure

**Option C: Hybrid (Balanced)**
1. Migrate to PostgreSQL
2. Use Gunicorn with `worker_class="gthread"` + `threads=4`
3. Multi-threaded single process = medium throughput
4. Easier than Celery, more robust than dev server
5. **Pros:** Good balance of simplicity and performance
6. **Cons:** Still one process, threads share CPU

---

## **Time Estimate**

- **Option A:** 2-4 hours (just DB migration)
- **Option B:** 20-30 hours (full refactor + testing)
- **Option C:** 4-6 hours (DB + Gunicorn config)

---

## **Conclusion**

✅ **The good news:** Polling architecture is inherently multi-process safe!

🔴 **The blocker:** Must migrate **SQLite → PostgreSQL** first

🟠 **Nice to have:** Replace threading with Celery for better reliability

🎯 **Start with:** PostgreSQL + Gunicorn (gthread), then add Celery later if needed
