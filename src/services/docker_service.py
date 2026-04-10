"""Docker service - Docker agent spawning and container management."""

import json
import re

import docker
from config import Config
from models.database import ExecutionDetails, Job
from repositories import ExecutionDetailsRepository

# Regex to strip ANSI escape sequences from container output
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


DOCKER_CLIENT = None
DOCKER_AVAILABLE = False

# Agent image definitions
AGENT_IMAGES = {
    "standard": {
        "tag": "paper-reproducibility-agent:latest",
        "dockerfile": "agent/Dockerfile",
        "environment_info": (
            "Python 3.11 container with pip, git, curl, and build-essential. "
            "Use pip to install any Python dependencies."
        ),
    },
    "ml": {
        "tag": "paper-reproducibility-agent-ml:latest",
        "dockerfile": "agent/Dockerfile.ml",
        "environment_info": (
            "Python 3.11 ML container. Pre-installed: PyTorch, scikit-learn, scipy, "
            "numpy, pandas, matplotlib. Use pip to install additional Python packages."
        ),
    },
    "matlab": {
        "tag": "paper-reproducibility-agent-matlab:latest",
        "dockerfile": "agent/Dockerfile.matlab",
        "environment_info": (
            "Python 3.11 + GNU Octave container (MATLAB-compatible). "
            "Pre-installed: octave, octave-signal, octave-statistics, octave-image, "
            "octave-io, octave-optim, octave-control. Also: numpy, scipy, matplotlib, oct2py. "
            "Run .m scripts with: octave --no-gui --eval \"run('script.m')\" "
            "Do NOT attempt to install MATLAB or Octave — Octave is already installed."
        ),
    },
}


def init_docker():
    """Initialize Docker client."""
    global DOCKER_CLIENT, DOCKER_AVAILABLE
    try:
        DOCKER_CLIENT = docker.from_env()
        DOCKER_AVAILABLE = True
        return True
    except Exception:
        DOCKER_AVAILABLE = False
        return False


def is_docker_available():
    """Check if Docker is available."""
    return DOCKER_AVAILABLE


def get_docker_client():
    """Get Docker client instance."""
    return DOCKER_CLIENT


def validate_network(network_name, app_logger=None):
    """
    Validate that a Docker network exists.

    Returns: (exists: bool, error_message: str)
    """
    if not DOCKER_AVAILABLE:
        return False, "Docker not available"

    try:
        networks = DOCKER_CLIENT.networks.list()
        network_names = [n.name for n in networks]

        if network_name in network_names:
            return True, None
        else:
            msg = (
                f"Docker network '{network_name}' not found. Available networks: {', '.join(network_names)}. "
                f"Create it with: docker network create {network_name}"
            )
            if app_logger:
                app_logger.error(msg)
            return False, msg
    except Exception as e:
        msg = f"Failed to validate Docker network: {e}"
        if app_logger:
            app_logger.error(msg)
        return False, msg


def build_agent_image(image_type="standard", app_logger=None):
    """Build Docker image for agent sandbox.

    Args:
        image_type: "standard" or "ml"
        app_logger: Flask app logger
    """
    if not DOCKER_AVAILABLE:
        return False

    image_config = AGENT_IMAGES.get(image_type)
    if not image_config:
        if app_logger:
            app_logger.error(f"✗ Unknown agent image type: {image_type}")
        return False

    try:
        if app_logger:
            app_logger.info(f"Building agent Docker image ({image_type})...")

        DOCKER_CLIENT.images.build(
            path=".", dockerfile=image_config["dockerfile"], tag=image_config["tag"], quiet=False
        )

        if app_logger:
            app_logger.info(f"✓ Agent image ({image_type}) built successfully")

        return True
    except Exception as e:
        if app_logger:
            app_logger.error(f"✗ Failed to build agent image ({image_type}): {e}")
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
            emit_event(job_id, {"step": "error", "message": "Docker not available for agent execution"})
        return False

    # Use defaults if config not provided
    if config is None:
        config = {"storage_limit": 10, "memory_limit": 4096, "cpu_limit": 2, "max_iterations": 15}

    # Check cache: if we've analyzed this repo before, reuse results
    # ONLY if caching is enabled
    if Config.ENABLE_CACHING:
        try:
            # Find previous jobs with artifacts matching this repo URL
            jobs_with_repo = list(Job.select().where(Job.report.contains(repo_url)))

            if jobs_with_repo:
                # Find first job with execution details
                cached_details = None
                for prev_job in jobs_with_repo:
                    try:
                        cached_details = ExecutionDetailsRepository.get(prev_job.id)
                        if cached_details:
                            break
                    except Exception:
                        continue

                if cached_details:
                    if app_logger:
                        app_logger.info(f"[{job_id}] Cache hit for {repo_url} - reusing execution results")
                    if emit_event:
                        emit_event(job_id, {"step": "cache_hit", "message": f"Using cached results for {repo_url}"})

                    # Copy cached results to new job
                    ExecutionDetails.create(
                        job_id=job_id,
                        commands_run=cached_details.commands_run,
                        stdout_combined=cached_details.stdout_combined,
                        actual_results=cached_details.actual_results,
                        dependencies_used=cached_details.dependencies_used,
                        errors_summary=cached_details.errors_summary,
                        discovered_files=cached_details.discovered_files,
                        test_info=cached_details.test_info,
                        randomness_info=cached_details.randomness_info,
                    )

                    if emit_event:
                        emit_event(job_id, {"step": "agent_completed", "message": "Cached agent results applied"})

                    return True
        except Exception:
            pass  # Continue with normal flow if cache lookup fails

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
            emit_event(job_id, {"step": "spawning_agent", "message": f"Spawning agent container for: {repo_url}"})

        # Determine which agent image to use
        image_type = config.get("docker_image", "standard")
        if image_type not in AGENT_IMAGES:
            if app_logger:
                app_logger.warning(f"[{job_id}] Unknown image type '{image_type}', falling back to standard")
            image_type = "standard"
        image_tag = AGENT_IMAGES[image_type]["tag"]

        if app_logger:
            app_logger.info(f"[{job_id}] Using agent image: {image_tag}")

        # Verify image exists
        try:
            DOCKER_CLIENT.images.get(image_tag)
            if app_logger:
                app_logger.info(f"[{job_id}] Agent image verified")
        except Exception as e:
            if app_logger:
                app_logger.warning(f"[{job_id}] Agent image not found, attempting build: {e}")
            build_agent_image(image_type, app_logger)

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

        # Get active execution checks for this user
        try:
            job = Job.get_by_id(job_id)
            user_id = job.user_id

            from services.check_service import CheckService

            active_checks = CheckService.get_active_checks_for_user(user_id)

            checks_data = {}
            for check in active_checks:
                checks_data[check["script_hash"]] = {"name": check["name"], "script_text": check["script_text"]}

            if app_logger:
                app_logger.info(f"[{job_id}] Found {len(checks_data)} active checks for user")
        except Exception as e:
            if app_logger:
                app_logger.warning(f"[{job_id}] Failed to get active checks: {e}, using all checks")

            # Fallback: use all checks if lookup fails
            from models.check import Check

            checks_list = list(Check.select())
            checks_data = {}
            for check in checks_list:
                checks_data[check.script_hash] = {"name": check.name, "script_text": check.script_text}

        # Memory and CPU limits from config
        memory_limit_mb = config.get("memory_limit", 2048)
        try:
            memory_limit_mb = int(memory_limit_mb)
            if memory_limit_mb < 512 or memory_limit_mb > 32768:
                if app_logger:
                    app_logger.warning(
                        f"[{job_id}] Memory limit {memory_limit_mb}MB out of range, using default 2048MB"
                    )
                memory_limit_mb = 2048
        except (ValueError, TypeError):
            memory_limit_mb = 2048
        memory_limit_str = f"{memory_limit_mb}m"

        max_iterations = config.get("max_iterations", 15)
        cpu_limit = config.get("cpu_limit", 2)

        # Container environment info for the agent prompt
        environment_info = AGENT_IMAGES.get(image_type, {}).get("environment_info", "")
        agent_instructions = config.get("agent_instructions", "")

        # Prepare network configuration
        # If DOCKER_NETWORK is empty, Docker uses default bridge network
        container_kwargs = {
            "detach": True,
            "name": container_name,
            "environment": {
                "REPO_URL": repo_url,
                "JOB_ID": job_id,
                "BACKEND_URL": backend_url,
                "STORAGE_LIMIT": storage_limit_str,
                "MAX_ITERATIONS": str(max_iterations),
                "CHECKS": json.dumps(checks_data),
                "CONTAINER_INFO": environment_info,
                "AGENT_INSTRUCTIONS": agent_instructions,
            },
            "mem_limit": memory_limit_str,
            "memswap_limit": memory_limit_str,
            "nano_cpus": int(cpu_limit * 1e9),
            "tmpfs": {"/tmp": f"size={storage_limit_str}"},
            "remove": False,
            "stdout": True,
            "stderr": True,
        }

        # Only validate and use custom network if specified
        if Config.DOCKER_NETWORK:
            network_valid, network_error = validate_network(Config.DOCKER_NETWORK, app_logger)
            if not network_valid:
                if app_logger:
                    app_logger.error(f"[{job_id}] {network_error}")
                if emit_event:
                    emit_event(
                        job_id, {"step": "error", "message": f"Docker network validation failed: {network_error}"}
                    )
                return False
            container_kwargs["network"] = Config.DOCKER_NETWORK
            if app_logger:
                app_logger.info(f"[{job_id}] Using Docker network: {Config.DOCKER_NETWORK}")
        else:
            if app_logger:
                app_logger.info(f"[{job_id}] Using Docker default bridge network")

        if app_logger:
            app_logger.info(f"[{job_id}] Starting container with storage limit: {storage_limit}GB")

        # Run agent container
        container = DOCKER_CLIENT.containers.run(image_tag, **container_kwargs)

        if app_logger:
            app_logger.info(f"[{job_id}] Container created and started: {container.id[:12]}")

        try:
            # Wait for container to complete and stream logs
            if app_logger:
                app_logger.info(f"[{job_id}] Waiting for container to complete...")

            line_count = 0
            for line in container.logs(stream=True, follow=True):
                message = line.decode("utf-8").strip()
                if message:
                    # Strip ANSI color codes from container output
                    message = ANSI_ESCAPE_RE.sub("", message)
                    line_count += 1
                    if app_logger:
                        app_logger.info(f"[{job_id}] [Agent] {message}")
                    if emit_event:
                        emit_event(job_id, {"step": "agent_output", "message": message})

            # Wait for container to exit
            result = container.wait(timeout=30)
            exit_code = result.get("StatusCode", -1)

            if app_logger:
                app_logger.info(f"[{job_id}] Container exited with code: {exit_code}")
                app_logger.info(f"[{job_id}] === Agent Container Success ===")

            if emit_event:
                emit_event(job_id, {"step": "agent_completed", "message": "Agent completed analysis"})

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
            emit_event(job_id, {"step": "error", "message": f"Agent execution failed: {str(e)}"})

        return False
