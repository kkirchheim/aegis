#!/usr/bin/env python3
"""
Paper Reproducibility Agent - Runs in Docker sandbox
Clones repos, executes user scripts, installs dependencies, executes code, reports results.
All execution happens in container (sandbox).
"""

import os
import sys
import json
import subprocess
import shlex
from pathlib import Path
import requests
import time
from typing import Optional, Dict, Any

# Configuration from environment
REPO_URL = os.getenv("REPO_URL", "")
JOB_ID = os.getenv("JOB_ID", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://host.docker.internal:5000")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "15"))
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


def execute_command(command: str, cwd: Optional[str] = None, shell: bool = True) -> Dict[str, Any]:
    """
    Execute a shell command in sandbox.
    CRITICAL: All execution happens in container, never on host.
    
    Args:
        command: Command to execute (bash syntax with pipes, redirects, etc.)
        cwd: Working directory (default: repo root)
        shell: Whether to use shell (True to support pipes, redirects, &&, ||, etc.)
    
    Returns:
        Dict with: {success, stdout, stderr, returncode}
    """
    if not cwd:
        cwd = REPO_PATH
    
    log_message(f"$ {command}")

    try:
        # Use pipefail so piped commands report the real exit code
        wrapped = f"set -o pipefail; {command}"
        result = subprocess.run(
            wrapped,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            shell=True,
            executable="/bin/bash"
        )

        success = result.returncode == 0

        # Log output once (log_message prints to stdout AND posts to backend)
        if result.stdout:
            log_message(result.stdout[:2000].rstrip(), severity="info")

        if result.stderr:
            log_message(result.stderr[:2000].rstrip(), severity="warning" if success else "error")

        output = {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:5000]
        }

        if success:
            log_message(f"✓ Exit code 0", severity="info")
        else:
            log_message(f"✗ Exit code {result.returncode}", severity="error")
        
        return output
        
    except subprocess.TimeoutExpired:
        log_message(f"✗ Command timed out after {COMMAND_TIMEOUT}s", severity="error")
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {COMMAND_TIMEOUT}s"
        }
    except Exception as e:
        log_message(f"✗ Error executing command: {e}", severity="error")
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }

def read_file(path: str, start_line: int = 1, max_lines: int = 200) -> Optional[str]:
    """Read file from repo (sandbox).

    Args:
        path: Relative path inside REPO_PATH.
        start_line: 1-based line number to start reading from.
        max_lines: Maximum number of lines to return.
    """
    full_path = Path(REPO_PATH) / path

    # Security: Prevent path traversal
    try:
        if not full_path.resolve().is_relative_to(Path(REPO_PATH).resolve()):
            log_message(f"✗ Path traversal attempt blocked: {path}", severity="error")
            return None
    except ValueError:
        if not str(full_path.resolve()).startswith(str(Path(REPO_PATH).resolve())):
            log_message(f"✗ Path traversal attempt blocked: {path}", severity="error")
            return None

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            total = len(all_lines)
            start_idx = max(0, start_line - 1)
            selected = all_lines[start_idx:start_idx + max_lines]
            content = ''.join(selected)
            shown_end = start_idx + len(selected)
            log_message(f"Read lines {start_idx+1}-{shown_end} of {total} from {path}")
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
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"✗ Backend returned {response.status_code}", severity="error")
            return None
            
    except requests.RequestException as e:
        log_message(f"✗ Backend communication error: {e}", severity="error")
        return None


def report_execution_details(state: Dict[str, Any]) -> bool:
    """Report collected execution details to backend for evaluation."""
    try:
        # Compile execution details from state
        execution_details = {
            "job_id": JOB_ID,
            "commands_run": "\n".join(state.get("executed_commands", [])),
            "stdout_combined": state.get("combined_output", ""),
            "actual_results": parse_actual_results(state.get("combined_output", "")),
            "dependencies_used": get_installed_packages(),
            "errors_summary": format_errors(state.get("errors", [])),
            "discovered_files": state.get("discovered_files", []),
            "test_info": check_for_tests(),
            "randomness_info": check_for_randomness_seeds()
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/agent/execution",
            json=execution_details,
            timeout=10
        )
        
        if response.status_code == 200:
            log_message(f"✓ Execution details reported to backend", severity="info")
            return True
        else:
            log_message(f"✗ Backend returned {response.status_code} for execution details", severity="error")
            return False
            
    except requests.RequestException as e:
        log_message(f"✗ Failed to report execution details: {e}", severity="error")
        return False


def get_installed_packages() -> str:
    """Get list of installed Python packages and requirements files."""
    details = []
    
    try:
        # Get pip list
        result = subprocess.run(
            "pip list",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        details.append("INSTALLED PACKAGES:\n" + result.stdout[:1500])
    except Exception as e:
        details.append(f"Failed to get package list: {e}")
    
    # Try to read requirements.txt
    for req_file in ["requirements.txt", "setup.py", "environment.yml", "Pipfile"]:
        try:
            path = Path(REPO_PATH) / req_file
            if path.exists():
                with open(path, 'r') as f:
                    content = f.read()[:1000]
                    details.append(f"\n{req_file}:\n{content}")
                    break  # Only show first found file
        except Exception as e:
            details.append(f"Failed to read {req_file}: {e}")
    
    return "\n".join(details)[:3000]  # Limit to 3000 chars total


def parse_actual_results(output: str) -> Dict[str, Any]:
    """Extract key results from execution output (accuracy, metrics, etc.)."""
    results = {}
    
    # Look for accuracy
    import re
    accuracy_match = re.search(r'(?:accuracy|test_acc|val_acc)[:\s=]+([0-9.]+)', output.lower())
    if accuracy_match:
        try:
            results["accuracy"] = float(accuracy_match.group(1))
        except:
            pass
    
    # Look for loss
    loss_match = re.search(r'(?:loss|test_loss|val_loss)[:\s=]+([0-9.]+)', output.lower())
    if loss_match:
        try:
            results["loss"] = float(loss_match.group(1))
        except:
            pass
    
    # Look for F1 score
    f1_match = re.search(r'(?:f1|f1-score)[:\s=]+([0-9.]+)', output.lower())
    if f1_match:
        try:
            results["f1_score"] = float(f1_match.group(1))
        except:
            pass
    
    return results


def format_errors(errors: list) -> str:
    """Format error list for readability."""
    if not errors:
        return "No errors"
    
    formatted = []
    for err in errors[-5:]:  # Last 5 errors
        cmd = err.get("command", "unknown")[:100]
        stderr = err.get("stderr", "unknown")[:200]
        formatted.append(f"- {cmd}: {stderr}")
    
    return "\n".join(formatted)


def check_for_tests() -> str:
    """Check if tests are present and try to run them."""
    findings = []
    
    # Check for test files/directories
    test_patterns = ["test_*.py", "*_test.py", "tests/", "test/"]
    has_tests = False
    
    try:
        for file in Path(REPO_PATH).rglob("*"):
            if any(pattern in str(file) for pattern in test_patterns):
                has_tests = True
                findings.append(f"Found test: {file.name}")
                break
    except Exception as e:
        findings.append(f"Error checking for tests: {e}")
    
    # Try to run tests if pytest available
    if has_tests:
        try:
            result = subprocess.run(
                f"cd {REPO_PATH} && python -m pytest --co -q 2>/dev/null | head -10",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout:
                findings.append(f"Pytest found: {result.stdout[:200]}")
        except:
            pass
    
    if not findings:
        findings.append("No test files detected")
    
    return "\n".join(findings)


def check_for_randomness_seeds() -> str:
    """Check if random seeds are set in code."""
    findings = []
    seed_patterns = [
        "np.random.seed",
        "tf.set_seed",
        "torch.manual_seed",
        "random.seed"
    ]
    
    try:
        for file in Path(REPO_PATH).rglob("*.py"):
            if file.is_file():
                try:
                    with open(file, 'r') as f:
                        content = f.read()
                        for pattern in seed_patterns:
                            if pattern in content:
                                findings.append(f"Found seed: {pattern} in {file.name}")
                                break
                except:
                    pass
    except Exception as e:
        findings.append(f"Error checking for seeds: {e}")
    
    if not findings:
        findings.append("No random seeds detected in code")
    
    return "\n".join(findings)


def build_reproducibility_plugins(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build reproducibility plugins array from analysis state."""
    plugins = {
        "plugins": [
            {
                "id": "code_availability",
                "name": "Code Availability",
                "category": "code",
                "status": "available" if state.get("repo_url") else "missing",
                "value": state.get("repo_url", "No code artifact found"),
                "severity": "high",
                "emoji": "📦"
            },
            {
                "id": "execution_success",
                "name": "Execution Status",
                "category": "code",
                "status": "passed" if len(state.get("errors", [])) == 0 else "failed",
                "value": f"Completed with {len(state.get('errors', []))} error(s)" if state.get("errors") else "Executed successfully",
                "severity": "high",
                "emoji": "✓"
            },
            {
                "id": "file_discovery",
                "name": "Repository Exploration",
                "category": "code",
                "status": "documented" if state.get("discovered_files") else "unknown",
                "value": f"Found {len(state.get('discovered_files', []))} files in repository",
                "severity": "medium",
                "emoji": "📁"
            }
        ]
    }
    return plugins

def report_completion(success: bool, message: str = "", accuracy: Optional[float] = None, state: Optional[Dict[str, Any]] = None):
    """Report completion back to backend to terminate agent loop."""
    try:
        payload = {
            "job_id": JOB_ID,
            "success": success,
            "message": message or ("Analysis completed successfully" if success else "Analysis failed"),
            "accuracy": accuracy
        }
        
        # Add reproducibility aspects if state is provided
        if state:
            payload["reproducibility_plugins"] = build_reproducibility_plugins(state)
        
        response = requests.post(
            f"{BACKEND_URL}/api/agent/complete",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            log_message(f"✓ Completion reported to backend: {'SUCCESS' if success else 'FAILED'}", severity="info")
            return True
        else:
            log_message(f"✗ Backend returned {response.status_code} for completion report", severity="error")
            return False
            
    except requests.RequestException as e:
        log_message(f"✗ Failed to report completion: {e}", severity="error")
        return False

def validate_repo_url(url):
    """Validate that the repository URL is safe to clone.

    Only allow http(s) and git:// schemes. Block shell metacharacters,
    local file:// URLs, and private/link-local IP ranges.
    """
    import re
    from urllib.parse import urlparse

    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"

    # Block shell metacharacters before any parsing
    dangerous_chars = set(';|&$`(){}!#\n\r')
    if dangerous_chars & set(url):
        return False, "URL contains disallowed characters"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL"

    # Only allow safe schemes
    if parsed.scheme not in ('http', 'https', 'git'):
        return False, f"Disallowed URL scheme: {parsed.scheme}"

    # Must have a hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Block localhost and private IPs (SSRF prevention)
    import ipaddress
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "URL points to a private/reserved address"
    except ValueError:
        # hostname is not an IP — that's fine, it's a domain name
        pass

    # Block localhost by name
    if hostname.lower() in ('localhost', 'host.docker.internal'):
        return False, "URL points to localhost"

    return True, None


def clone_repository():
    """Clone repository into sandbox."""
    log_message(f"🔍 Cloning repository: {REPO_URL}")

    # Validate URL before cloning
    is_valid, reason = validate_repo_url(REPO_URL)
    if not is_valid:
        log_message(f"✗ Invalid repository URL: {reason}", severity="error")
        return False

    # Create workspace directory
    os.makedirs(REPO_PATH, exist_ok=True)

    # Use shlex.quote to prevent command injection
    result = execute_command(f"git clone {shlex.quote(REPO_URL)} {shlex.quote(REPO_PATH)}")

    if not result["success"]:
        log_message(f"✗ Failed to clone repository", severity="error")
        return False

    log_message(f"✓ Repository cloned successfully")
    return True


def run_checks():
    """Execute all checks from CHECKS environment variable.

    Run user-provided checks before Claude loop.
    Checks are identified by hash and stored in /workspace/checks/{hash}.
    Results are reported to /agent/check_result endpoint.
    """
    checks_json = os.getenv('CHECKS', '{}')

    if not checks_json or checks_json == '{}':
        log_message("No execution checks to run (CHECKS not set)")
        return

    try:
        checks = json.loads(checks_json)
    except json.JSONDecodeError:
        log_message(f"Error: Invalid CHECKS JSON: {checks_json}", severity="error")
        return

    if not checks:
        log_message("No execution checks to run")
        return

    log_message(f"🔬 Running {len(checks)} execution check(s)...")

    # Create checks directory (in /workspace where agent user has write permission)
    checks_dir = Path('/workspace/checks')
    checks_dir.mkdir(exist_ok=True, parents=True)

    for script_hash, check_data in checks.items():
        check_name = check_data.get('name', script_hash[:8])
        script_text = check_data.get('script_text', '')

        log_message(f"Running check: {check_name}")

        try:
            # Write script to file
            script_path = checks_dir / script_hash
            script_path.write_text(script_text)

            # Make executable
            os.chmod(script_path, 0o755)

            # Execute check
            start_time = time.time()

            result = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=REPO_PATH
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Log output
            if result.stdout:
                log_message(f"Output: {result.stdout}")
            if result.stderr:
                log_message(f"Stderr: {result.stderr}", severity="warning")

            # Report result to backend
            report_check_result(
                script_hash=script_hash,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms
            )

            log_message(f"Check complete: {check_name} (exit {result.returncode})")

        except subprocess.TimeoutExpired:
            log_message(f"Check timeout: {check_name}", severity="error")
            report_check_result(
                script_hash=script_hash,
                exit_code=124,
                stdout="",
                stderr="Check timeout after 5 minutes",
                duration_ms=300000
            )

        except Exception as e:
            log_message(f"Check error: {check_name} - {str(e)}", severity="error")
            report_check_result(
                script_hash=script_hash,
                exit_code=127,
                stdout="",
                stderr=str(e),
                duration_ms=0
            )


def report_check_result(script_hash: str, exit_code: int, stdout: str,
                        stderr: str, duration_ms: int):
    """Report check result back to backend."""
    try:
        payload = {
            'job_id': JOB_ID,
            'script_hash': script_hash,
            'exit_code': exit_code,
            'stdout': stdout[:5000],  # Limit size
            'stderr': stderr[:5000],
            'duration_ms': duration_ms
        }

        response = requests.post(
            f"{BACKEND_URL}/api/agent/check_result",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            log_message(f"Reported check result: {script_hash[:8]}")
        else:
            log_message(f"Failed to report check result: {response.status_code}", severity="error")

    except Exception as e:
        log_message(f"Error reporting check result: {str(e)}", severity="error")


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
    
    # Step 2: Run execution checks (if any)
    run_checks()
    
    # Initialize state
    state = {
        "repo_url": REPO_URL,
        "current_directory": ".",
        "discovered_files": [],
        "environment": {},
        "last_command": None,
        "last_output": None,
        "errors": [],
        "iteration": 0,
        "max_iterations": MAX_ITERATIONS,
        "executed_commands": [],  # Track all commands
        "combined_output": ""     # Accumulate all output
    }
    
    # Step 3: List files in repo
    state["discovered_files"] = list_files(".")
    log_message(f"📁 Found {len(state['discovered_files'])} files in repo root")
    print(f"   Files: {', '.join(state['discovered_files'][:5])}...")
    print()
    
    # Step 4: Agent loop (Claude decision loop)
    iteration = 0
    completed = False  # Track whether agent reported completion itself
    exit_reason = ""
    exit_success = False
    consecutive_reads = 0  # Track consecutive read_file actions (debugging detection)
    read_files_set = set()  # Track which files have been read
    failed_commands = set()  # Track commands that already failed

    while iteration < MAX_ITERATIONS:
        iteration += 1
        state["iteration"] = iteration

        print(f"{Color.YELLOW}--- Iteration {iteration}/{MAX_ITERATIONS} ---{Color.RESET}")

        # Ask Claude what to do
        decision = ask_claude(state)

        if not decision:
            log_message("Failed to get decision from Claude", severity="error")
            exit_reason = "Backend communication failed"
            break

        action = decision.get("action", "done")
        target = decision.get("target", "")
        reasoning = decision.get("reasoning", "")

        print(f"Action: {action}")
        print(f"Reasoning: {reasoning}")
        print()

        # --- Guardrail: detect debugging loops ---
        if action == "read_file":
            consecutive_reads += 1
            file_key = target.split(":")[0] if ":" in target else target
            # Block re-reading the same source file (allow README, docs, configs)
            is_doc_file = any(p in file_key.lower() for p in [
                "readme", "setup", "config", "requirements", "environment",
                "makefile", "dockerfile", ".cfg", ".ini", ".toml", ".yml", ".yaml"
            ])
            if file_key in read_files_set and not is_doc_file:
                log_message(f"⚠ Skipping re-read of {file_key} (already read)", severity="warning")
                state["last_output"] = f"[AGENT] Already read {file_key}. Move on to the next script or report results."
                state["combined_output"] += f"\n[AGENT] Skipped re-read of {file_key}\n"
                continue
            read_files_set.add(file_key)

            if consecutive_reads >= 3:
                log_message(f"⚠ 3 consecutive reads detected — forcing agent to act or report", severity="warning")
                state["last_output"] = "[AGENT] Too many consecutive file reads. Run a script or report results."
                state["combined_output"] += "\n[AGENT] Forced: stop reading, run something or report results.\n"
                consecutive_reads = 0
                continue
        else:
            consecutive_reads = 0

        # --- Guardrail: block diagnostic python -c commands (debugging) ---
        if action == "run_command" and target.strip().startswith("python -c") and iteration > 5:
            log_message(f"⚠ Blocking diagnostic command (no debugging)", severity="warning")
            state["last_output"] = "[AGENT] Diagnostic commands are not allowed. Run actual scripts or report results."
            state["combined_output"] += f"\n[AGENT] Blocked diagnostic: {target[:80]}\n"
            continue

        # Execute action
        if action == "read_file":
            # Support "path:start_line" syntax (e.g. "models/foo.py:80")
            start_line = 1
            file_path = target
            if ":" in target:
                parts = target.rsplit(":", 1)
                if parts[1].isdigit():
                    file_path = parts[0]
                    start_line = int(parts[1])
            log_message(f"📖 Reading file: {file_path} (from line {start_line})")
            content = read_file(file_path, start_line=start_line)
            if content:
                state["last_output"] = content
                state["last_command"] = f"read_file({target})"
                # Add to combined output history
                state["executed_commands"].append(f"read_file({target})")
                state["combined_output"] += f"\n--- Reading file: {file_path} (lines {start_line}+) ---\n"
                state["combined_output"] += content + "\n"

        elif action == "run_command":
            state["last_command"] = target
            result = execute_command(target)
            state["last_output"] = result.get("stdout", "") + result.get("stderr", "")

            # Track command and output for execution details
            state["executed_commands"].append(target)
            state["combined_output"] += f"\n$ {target}\n"
            state["combined_output"] += result.get("stdout", "")
            if result.get("stderr"):
                state["combined_output"] += f"[STDERR] {result.get('stderr')}\n"

            if not result["success"]:
                state["errors"].append({
                    "command": target,
                    "returncode": result["returncode"],
                    "stderr": result["stderr"]
                })
                failed_commands.add(target)

        elif action == "check_success":
            log_message("✓ Reproducibility check passed!")
            completed = True
            exit_success = True
            exit_reason = reasoning
            break

        elif action == "done":
            log_message(f"✓ Agent completed analysis (iteration {iteration})")
            completed = True
            exit_success = len(state["errors"]) == 0
            exit_reason = reasoning or "Analysis completed"
            break

        else:
            log_message(f"Unknown action: {action}", severity="error")
            exit_reason = f"Unknown action: {action}"
            break

        print()

    if not completed and iteration >= MAX_ITERATIONS:
        exit_reason = f"Max iterations ({MAX_ITERATIONS}) reached. {len(state['errors'])} errors encountered."
        log_message(f"⚠ {exit_reason}", severity="warn")

    # Always report execution details and completion, regardless of how we exited
    report_execution_details(state)
    report_completion(
        success=exit_success,
        message=exit_reason,
        state=state
    )
    
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
