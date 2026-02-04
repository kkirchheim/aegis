"""Docker service - Docker agent spawning and container management."""

import os
import hashlib
import docker
import json
from database import get_db
from config import Config


DOCKER_CLIENT = None
DOCKER_AVAILABLE = False


def init_docker():
    """Initialize Docker client."""
    global DOCKER_CLIENT, DOCKER_AVAILABLE
    try:
        DOCKER_CLIENT = docker.from_env()
        DOCKER_AVAILABLE = True
        return True
    except Exception as e:
        DOCKER_AVAILABLE = False
        return False


def is_docker_available():
    """Check if Docker is available."""
    return DOCKER_AVAILABLE


def get_docker_client():
    """Get Docker client instance."""
    return DOCKER_CLIENT


def build_agent_image(app_logger=None):
    """Build Docker image for agent sandbox."""
    if not DOCKER_AVAILABLE:
        return False
    
    try:
        if app_logger:
            app_logger.info("Building agent Docker image...")
        
        DOCKER_CLIENT.images.build(
            path=".",
            dockerfile="Dockerfile.agent",
            tag="paper-reproducibility-agent:latest",
            quiet=False
        )
        
        if app_logger:
            app_logger.info("✓ Agent image built successfully")
        
        return True
    except Exception as e:
        if app_logger:
            app_logger.error(f"✗ Failed to build agent image: {e}")
        return False


def spawn_agent_container(job_id, repo_url, config=None, app_logger=None, emit_event=None):
    """
    Spawn Docker container to run agent on repository.
    
    Args:
        job_id: Unique job identifier
        repo_url: Repository URL to analyze
        config: Optional configuration dict
        app_logger: Flask app logger
        emit_event: Event emission function
    """
    if not DOCKER_AVAILABLE:
        if app_logger:
            app_logger.error("Docker not available")
        if emit_event:
            emit_event(job_id, {
                "step": "error",
                "message": "Docker not available for agent execution"
            })
        return False
    
    # Use defaults if config not provided
    if config is None:
        config = {
            "storage_limit": 10,
            "memory_limit": 2048,
            "cpu_limit": 2
        }
    
    # Check cache: if we've analyzed this repo before, reuse results
    cache_key = hashlib.md5(repo_url.encode()).hexdigest()
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM execution_details WHERE job_id IN (SELECT id FROM jobs WHERE report LIKE ?)",
        (f'%"url": "{repo_url}"%',)
    )
    cached = c.fetchone()
    conn.close()
    
    if cached:
        if app_logger:
            app_logger.info(f"[{job_id}] Cache hit for {repo_url} - reusing execution results")
        if emit_event:
            emit_event(job_id, {
                "step": "cache_hit",
                "message": f"Using cached results for {repo_url}"
            })
        
        # Copy cached results to new job
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO execution_details 
            (job_id, commands_run, stdout_combined, actual_results, dependencies_used, errors_summary, discovered_files, test_info, randomness_info)
            SELECT ?, commands_run, stdout_combined, actual_results, dependencies_used, errors_summary, discovered_files, test_info, randomness_info
            FROM execution_details WHERE id = ?
        """, (job_id, cached['id']))
        conn.commit()
        conn.close()
        
        if emit_event:
            emit_event(job_id, {
                "step": "agent_completed",
                "message": "Cached agent results applied"
            })
        
        return True
    
    try:
        container_name = f"agent-{job_id[:8]}"
        
        if app_logger:
            app_logger.info(f"[{job_id}] === Agent Container Spawn ===")
            app_logger.info(f"[{job_id}] Repository: {repo_url}")
        
        # Backend URL for agent
        backend_url = Config.DOCKER_BACKEND_URL
        
        if app_logger:
            app_logger.info(f"[{job_id}] Backend URL for agent: {backend_url}")
            app_logger.info(f"[{job_id}] Container name: {container_name}")
        
        if emit_event:
            emit_event(job_id, {
                "step": "spawning_agent",
                "message": f"Spawning agent container for: {repo_url}"
            })
        
        # Verify image exists
        try:
            DOCKER_CLIENT.images.get("paper-reproducibility-agent:latest")
            if app_logger:
                app_logger.info(f"[{job_id}] Agent image verified")
        except Exception as e:
            if app_logger:
                app_logger.warning(f"[{job_id}] Agent image not found, attempting build: {e}")
            build_agent_image(app_logger)
        
        # Validate storage limit
        storage_limit = config.get("storage_limit", 10)
        try:
            storage_limit = int(storage_limit)
            if storage_limit < 1 or storage_limit > 100:
                if app_logger:
                    app_logger.warning(f"[{job_id}] Storage limit {storage_limit}GB out of range, using default 10GB")
                storage_limit = 10
        except (ValueError, TypeError):
            if app_logger:
                app_logger.warning(f"[{job_id}] Invalid storage limit, using default 10GB")
            storage_limit = 10
        
        storage_limit_str = f"{storage_limit}g"
        
        if app_logger:
            app_logger.info(f"[{job_id}] Starting container with storage limit: {storage_limit}GB")
        
        # Run agent container
        container = DOCKER_CLIENT.containers.run(
            "paper-reproducibility-agent:latest",
            detach=True,
            name=container_name,
            environment={
                "REPO_URL": repo_url,
                "JOB_ID": job_id,
                "BACKEND_URL": backend_url,
                "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
                "STORAGE_LIMIT": storage_limit_str
            },
            mem_limit="2g",
            memswap_limit="2g",
            nano_cpus=int(2 * 1e9),
            tmpfs={"/tmp": f"size={storage_limit_str}"},
            network=Config.DOCKER_NETWORK,
            remove=False,
            stdout=True,
            stderr=True
        )
        
        if app_logger:
            app_logger.info(f"[{job_id}] Container created and started: {container.id[:12]}")
        
        try:
            # Wait for container to complete and stream logs
            if app_logger:
                app_logger.info(f"[{job_id}] Waiting for container to complete...")
            
            line_count = 0
            for line in container.logs(stream=True):
                message = line.decode('utf-8').strip()
                if message:
                    line_count += 1
                    if app_logger:
                        app_logger.info(f"[{job_id}] [Agent] {message}")
                    if emit_event:
                        emit_event(job_id, {
                            "step": "agent_output",
                            "message": message
                        })
            
            # Wait for container to exit
            result = container.wait(timeout=30)
            exit_code = result.get("StatusCode", -1)
            
            if app_logger:
                app_logger.info(f"[{job_id}] Container exited with code: {exit_code}")
                app_logger.info(f"[{job_id}] === Agent Container Success ===")
            
            if emit_event:
                emit_event(job_id, {
                    "step": "agent_completed",
                    "message": "Agent completed analysis"
                })
            
            return True
        
        finally:
            # Clean up
            try:
                container.reload()
                if app_logger:
                    app_logger.info(f"[{job_id}] Cleaning up container...")
                container.stop(timeout=5)
                container.remove()
                if app_logger:
                    app_logger.info(f"[{job_id}] Container cleaned up successfully")
            except docker.errors.NotFound:
                if app_logger:
                    app_logger.info(f"[{job_id}] Container already removed")
            except Exception as e:
                if app_logger:
                    app_logger.warning(f"[{job_id}] Container cleanup warning: {e}")
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"[{job_id}] === Agent Container Failed ===")
            app_logger.error(f"[{job_id}] Exception: {type(e).__name__}: {str(e)}")
        
        if emit_event:
            emit_event(job_id, {
                "step": "error",
                "message": f"Agent execution failed: {str(e)}"
            })
        
        return False
