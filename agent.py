#!/usr/bin/env python3
"""
Paper Reproducibility Agent - Runs in Docker sandbox
Clones repos, installs dependencies, executes code, reports results.
All execution happens in container (sandbox).
"""

import os
import sys
import json
import subprocess
import shlex
from pathlib import Path
import requests
from typing import Optional, Dict, Any

# Configuration from environment
REPO_URL = os.getenv("REPO_URL", "")
JOB_ID = os.getenv("JOB_ID", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://host.docker.internal:5000")
MAX_ITERATIONS = 15
COMMAND_TIMEOUT = 300  # 5 minutes per command
REPO_PATH = "/workspace/repo"

# Color codes for terminal output
class Color:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

def log_message(message: str, severity: str = "info"):
    """Log message to backend via API."""
    print(f"{Color.BLUE}[{severity.upper()}]{Color.RESET} {message}")
    
    try:
        requests.post(
            f"{BACKEND_URL}/api/agent/log",
            json={
                "job_id": JOB_ID,
                "message": message,
                "severity": severity
            },
            timeout=5
        )
    except Exception as e:
        print(f"{Color.YELLOW}[WARN]{Color.RESET} Failed to log to backend: {e}")

def print_command(command: str):
    """Print command being executed (for debugging)."""
    print(f"{Color.CYAN}$ {command}{Color.RESET}")

def execute_command(command: str, cwd: Optional[str] = None, shell: bool = False) -> Dict[str, Any]:
    """
    Execute a shell command in sandbox.
    CRITICAL: All execution happens in container, never on host.
    
    Args:
        command: Command to execute
        cwd: Working directory (default: repo root)
        shell: Whether to use shell (avoid for security)
    
    Returns:
        Dict with: {success, stdout, stderr, returncode}
    """
    if not cwd:
        cwd = REPO_PATH
    
    print_command(command)
    log_message(f"Executing: {command}")
    
    try:
        result = subprocess.run(
            command if shell else shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            shell=shell
        )
        
        success = result.returncode == 0
        
        if result.stdout:
            print(f"{Color.GREEN}{result.stdout}{Color.RESET}")
        
        if result.stderr and result.returncode != 0:
            print(f"{Color.RED}{result.stderr}{Color.RESET}")
        
        output = {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],  # Truncate for safety
            "stderr": result.stderr[:2000]
        }
        
        if success:
            log_message(f"✓ Command succeeded", severity="success")
        else:
            log_message(f"✗ Command failed (exit code {result.returncode})", severity="error")
        
        return output
        
    except subprocess.TimeoutExpired:
        print(f"{Color.RED}Command timed out after {COMMAND_TIMEOUT}s{Color.RESET}")
        log_message(f"✗ Command timed out", severity="error")
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {COMMAND_TIMEOUT}s"
        }
    except Exception as e:
        print(f"{Color.RED}Error executing command: {e}{Color.RESET}")
        log_message(f"✗ Error executing command: {e}", severity="error")
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }

def read_file(path: str, max_lines: int = 100) -> Optional[str]:
    """Read file from repo (sandbox)."""
    full_path = Path(REPO_PATH) / path
    
    # Security: Prevent path traversal
    if not full_path.resolve().is_relative_to(Path(REPO_PATH).resolve()):
        log_message(f"✗ Path traversal attempt blocked: {path}", severity="error")
        return None
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[:max_lines]
            content = ''.join(lines)
            print(f"{Color.GREEN}Read {len(lines)} lines from {path}{Color.RESET}")
            return content
    except FileNotFoundError:
        log_message(f"✗ File not found: {path}", severity="error")
        return None
    except Exception as e:
        log_message(f"✗ Error reading file: {e}", severity="error")
        return None

def list_files(path: str = ".") -> list:
    """List files in repo directory (sandbox)."""
    target = Path(REPO_PATH) / path if path != "." else Path(REPO_PATH)
    
    try:
        items = []
        for item in sorted(target.iterdir())[:30]:  # Limit to 30 items
            rel_path = str(item.relative_to(REPO_PATH))
            if item.is_dir():
                items.append(f"{rel_path}/")
            else:
                items.append(rel_path)
        return items
    except Exception as e:
        log_message(f"✗ Error listing files: {e}", severity="error")
        return []

def ask_claude(state: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Ask Claude (via backend) what to do next."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/agent/think",
            json={
                "job_id": JOB_ID,
                "repo_state": state
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"✗ Backend returned {response.status_code}", severity="error")
            return None
            
    except requests.RequestException as e:
        log_message(f"✗ Backend communication error: {e}", severity="error")
        return None

def clone_repository():
    """Clone repository into sandbox."""
    log_message(f"🔍 Cloning repository: {REPO_URL}")
    
    # Create workspace directory
    os.makedirs(REPO_PATH, exist_ok=True)
    
    result = execute_command(f"git clone {REPO_URL} {REPO_PATH}")
    
    if not result["success"]:
        log_message(f"✗ Failed to clone repository", severity="error")
        return False
    
    log_message(f"✓ Repository cloned successfully")
    return True

def main():
    """Main agent loop."""
    print(f"{Color.CYAN}🦞 Paper Reproducibility Agent Starting{Color.RESET}")
    print(f"Job ID: {JOB_ID}")
    print(f"Repo URL: {REPO_URL}")
    print(f"Backend: {BACKEND_URL}")
    print()
    
    log_message(f"Agent starting - Repo: {REPO_URL}")
    
    # Step 1: Clone repository
    if not clone_repository():
        log_message("Agent failed to clone repository", severity="error")
        return 1
    
    # Initialize state
    state = {
        "repo_url": REPO_URL,
        "current_directory": ".",
        "discovered_files": [],
        "environment": {},
        "last_command": None,
        "last_output": None,
        "errors": [],
        "iteration": 0
    }
    
    # Step 2: List files in repo
    state["discovered_files"] = list_files(".")
    log_message(f"📁 Found {len(state['discovered_files'])} files in repo root")
    print(f"   Files: {', '.join(state['discovered_files'][:5])}...")
    print()
    
    # Step 3: Agent loop
    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1
        state["iteration"] = iteration
        
        print(f"{Color.YELLOW}--- Iteration {iteration}/{MAX_ITERATIONS} ---{Color.RESET}")
        
        # Ask Claude what to do
        decision = ask_claude(state)
        
        if not decision:
            log_message("Failed to get decision from Claude", severity="error")
            break
        
        action = decision.get("action", "done")
        target = decision.get("target", "")
        reasoning = decision.get("reasoning", "")
        
        print(f"Action: {action}")
        print(f"Reasoning: {reasoning}")
        print()
        
        # Execute action
        if action == "read_file":
            log_message(f"📖 Reading file: {target}")
            content = read_file(target, max_lines=100)
            if content:
                state["last_output"] = content
                state["last_command"] = f"read_file({target})"
            
        elif action == "run_command":
            state["last_command"] = target
            result = execute_command(target)
            state["last_output"] = result.get("stdout", "") + result.get("stderr", "")
            
            if not result["success"]:
                state["errors"].append({
                    "command": target,
                    "returncode": result["returncode"],
                    "stderr": result["stderr"]
                })
        
        elif action == "check_success":
            log_message("✓ Reproducibility check passed!")
            print()
            
        elif action == "done":
            log_message(f"✓ Agent completed analysis (iteration {iteration})")
            break
        
        else:
            log_message(f"Unknown action: {action}", severity="error")
            break
        
        print()
    
    if iteration >= MAX_ITERATIONS:
        log_message(f"⚠ Max iterations reached ({MAX_ITERATIONS})", severity="warn")
    
    # Final summary
    print(f"{Color.CYAN}=== Final Report ==={Color.RESET}")
    print(f"Iterations: {state['iteration']}")
    print(f"Files discovered: {len(state['discovered_files'])}")
    print(f"Errors encountered: {len(state['errors'])}")
    
    if state["errors"]:
        print(f"\n{Color.RED}Errors:{Color.RESET}")
        for err in state["errors"]:
            print(f"  - {err['command']}: {err['stderr'][:100]}")
    
    log_message(f"Agent completed. Errors: {len(state['errors'])}")
    return 0 if len(state['errors']) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
