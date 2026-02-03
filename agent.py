"""
Paper Reproducibility Agent

Runs inside Docker container. Clones repository and executes code with LLM guidance.
Communicates with backend Flask server via HTTP API.
"""

import os
import subprocess
import json
import time
import requests
from pathlib import Path

BACKEND_URL = os.getenv("BACKEND_URL", "http://host.docker.internal:5000")
REPO_URL = os.getenv("REPO_URL", "")
JOB_ID = os.getenv("JOB_ID", "")
MAX_ITERATIONS = 15

# State tracking
repo_state = {
    "stage": "initial",
    "cwd": "/workspace/repo",
    "files": [],
    "last_output": None,
    "last_command": None,
    "completed_steps": [],
    "errors": []
}


def log_to_backend(message):
    """Send progress message to backend."""
    try:
        requests.post(
            f"{BACKEND_URL}/api/agent/log",
            json={
                "job_id": JOB_ID,
                "message": message
            },
            timeout=10
        )
    except Exception as e:
        print(f"[ERROR] Failed to log to backend: {e}")


def ask_claude_what_to_do():
    """Call backend to ask Claude what action to take next."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/agent/think",
            json={
                "job_id": JOB_ID,
                "repo_state": repo_state
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Backend returned {response.status_code}: {response.text}")
            return None
        
        return response.json()
    
    except Exception as e:
        print(f"[ERROR] Failed to get Claude action: {e}")
        log_to_backend(f"Failed to reach backend: {e}")
        return None


def run_shell_command(cmd, timeout=60):
    """
    Execute shell command and capture output.
    
    Returns:
        {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=repo_state["cwd"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:],  # Last 2000 chars
            "stderr": result.stderr[-2000:]
        }
    
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timeout (>{timeout}s)"
        }
    
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }


def read_file(filepath):
    """Read file content."""
    try:
        full_path = Path(repo_state["cwd"]) / filepath
        
        # Security: prevent reading outside repo
        full_path = full_path.resolve()
        repo_path = Path(repo_state["cwd"]).resolve()
        
        if not str(full_path).startswith(str(repo_path)):
            return None
        
        if not full_path.exists():
            return None
        
        with open(full_path, "r", errors="ignore") as f:
            return f.read()[:5000]  # First 5000 chars
    
    except Exception as e:
        return None


def list_files(directory="."):
    """List files in directory."""
    try:
        full_path = Path(repo_state["cwd"]) / directory
        files = []
        
        for item in full_path.iterdir():
            if item.is_file() and not item.name.startswith("."):
                files.append(item.name)
        
        return sorted(files)[:50]  # First 50 files
    
    except Exception as e:
        return []


def agent_loop():
    """Main agent loop: ask Claude, execute, repeat."""
    
    print("[AGENT] Starting reproducibility agent...")
    log_to_backend("Agent: Starting...")
    
    # Step 1: Clone repository
    print(f"[AGENT] Cloning {REPO_URL}...")
    log_to_backend(f"Cloning repository: {REPO_URL}")
    
    clone_result = run_shell_command(f"git clone {REPO_URL} /workspace/repo")
    
    if clone_result["returncode"] != 0:
        print(f"[ERROR] Clone failed: {clone_result['stderr']}")
        log_to_backend(f"ERROR: Clone failed - {clone_result['stderr']}")
        repo_state["errors"].append(f"Clone failed: {clone_result['stderr'][:100]}")
        return
    
    # List initial files
    repo_state["files"] = list_files()
    log_to_backend(f"Repository cloned. Found {len(repo_state['files'])} files in root.")
    
    # Step 2: Agent loop
    for iteration in range(MAX_ITERATIONS):
        print(f"\n[AGENT] Iteration {iteration + 1}/{MAX_ITERATIONS}")
        
        # Ask Claude what to do
        action = ask_claude_what_to_do()
        
        if not action:
            log_to_backend("ERROR: Could not get Claude response")
            break
        
        action_type = action.get("action", "done")
        reasoning = action.get("reasoning", "")
        target = action.get("target", "")
        
        print(f"[CLAUDE] Action: {action_type}")
        print(f"[CLAUDE] Reasoning: {reasoning}")
        
        log_to_backend(f"Claude → {action_type}: {reasoning}")
        
        # Execute action
        if action_type == "read_file":
            print(f"[AGENT] Reading file: {target}")
            content = read_file(target)
            
            if content:
                repo_state["last_output"] = {"stdout": content}
                print(f"[AGENT] Read {len(content)} chars from {target}")
                log_to_backend(f"Read file {target} ({len(content)} chars)")
            else:
                repo_state["errors"].append(f"Could not read {target}")
                log_to_backend(f"ERROR: Could not read {target}")
        
        elif action_type == "run_command":
            print(f"[AGENT] Running: {target}")
            log_to_backend(f"Executing: {target}")
            
            result = run_shell_command(target)
            repo_state["last_output"] = result
            repo_state["last_command"] = target
            
            if result["returncode"] == 0:
                print(f"[SUCCESS] Command succeeded")
                log_to_backend(f"✓ Command succeeded")
                repo_state["completed_steps"].append(target)
            else:
                print(f"[ERROR] Command failed with code {result['returncode']}")
                error_msg = result.get("stderr", result.get("stdout", ""))
                log_to_backend(f"✗ Command failed: {error_msg[:100]}")
                repo_state["errors"].append(error_msg[:100])
        
        elif action_type == "check_success":
            print(f"[AGENT] Checking success")
            log_to_backend("Checking if execution was successful")
            # Claude has determined success
            print("[SUCCESS] Agent confirmed success")
            log_to_backend("✓ Code executed successfully!")
            break
        
        elif action_type == "done":
            print(f"[AGENT] Claude says done")
            log_to_backend("Agent completed analysis")
            break
        
        else:
            print(f"[AGENT] Unknown action: {action_type}")
            log_to_backend(f"Unknown action: {action_type}")
            break
        
        # Small delay between iterations
        time.sleep(1)
    
    print(f"\n[AGENT] Agent loop completed after {iteration + 1} iterations")
    print(f"[AGENT] Completed steps: {repo_state['completed_steps']}")
    print(f"[AGENT] Errors encountered: {repo_state['errors']}")


if __name__ == "__main__":
    print(f"[AGENT] Backend URL: {BACKEND_URL}")
    print(f"[AGENT] Repo URL: {REPO_URL}")
    print(f"[AGENT] Job ID: {JOB_ID[:8]}...")
    
    if not REPO_URL:
        print("[ERROR] REPO_URL environment variable not set")
        exit(1)
    
    if not JOB_ID:
        print("[ERROR] JOB_ID environment variable not set")
        exit(1)
    
    try:
        agent_loop()
    except Exception as e:
        print(f"[ERROR] Fatal error in agent: {e}")
        log_to_backend(f"FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
