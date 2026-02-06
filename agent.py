#!/usr/bin/env python3
"""Agent running in Docker container for code execution.

This agent:
1. Clones the repository
2. Executes user scripts (if provided)
3. Interacts with Claude LLM via backend API for decision-making
4. Reports execution results back to backend
"""

import os
import json
import sys
import subprocess
import time
import requests
from pathlib import Path


class Agent:
    """Agent running inside Docker container."""
    
    def __init__(self):
        self.job_id = os.getenv('JOB_ID')
        self.repo_url = os.getenv('REPO_URL')
        self.backend_url = os.getenv('BACKEND_URL')
        
        if not all([self.job_id, self.repo_url, self.backend_url]):
            raise ValueError("Missing required environment: JOB_ID, REPO_URL, BACKEND_URL")
        
        self.repo_path = Path('/workspace/repo')
        self.scripts = {}
        
        # Load scripts from environment
        scripts_json = os.getenv('SCRIPTS', '{}')
        try:
            self.scripts = json.loads(scripts_json)
        except json.JSONDecodeError:
            print(f"Error: Invalid SCRIPTS JSON: {scripts_json}")
            self.scripts = {}
    
    def log(self, message: str):
        """Log a message via backend."""
        try:
            requests.post(
                f"{self.backend_url}/agent/log",
                json={"job_id": self.job_id, "message": message},
                timeout=5
            )
        except:
            print(f"[LOG] {message}")
        
        # Also print locally for debugging
        print(f"[{self.job_id}] {message}")
    
    def clone_repo(self):
        """Clone the repository."""
        self.log("Cloning repository...")
        
        try:
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.repo_path)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            self.log("Repository cloned successfully")
            return True
        
        except Exception as e:
            self.log(f"Error cloning repository: {str(e)}")
            return False
    
    def run_scripts(self):
        """Execute all scripts and report results."""
        self.log(f"Preparing to run {len(self.scripts)} script(s)...")
        
        if not self.scripts:
            self.log("No scripts to execute")
            return
        
        # Create scripts directory
        scripts_dir = Path('/scripts')
        scripts_dir.mkdir(exist_ok=True)
        
        for script_hash, script_data in self.scripts.items():
            script_name = script_data.get('name', script_hash[:8])
            script_text = script_data.get('script_text', '')
            
            self.log(f"Running script: {script_name}")
            
            try:
                # Write script to file
                script_path = scripts_dir / script_hash
                script_path.write_text(script_text)
                
                # Make executable
                os.chmod(script_path, 0o755)
                
                # Execute script
                start_time = time.time()
                
                result = subprocess.run(
                    [str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=str(self.repo_path)
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Report result to backend
                self.report_script_result(
                    script_hash=script_hash,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=duration_ms
                )
                
                self.log(f"Script complete: {script_name} (exit {result.returncode})")
            
            except subprocess.TimeoutExpired:
                self.log(f"Script timeout: {script_name}")
                self.report_script_result(
                    script_hash=script_hash,
                    exit_code=124,
                    stdout="",
                    stderr="Script timeout after 5 minutes",
                    duration_ms=300000
                )
            
            except Exception as e:
                self.log(f"Script error: {script_name} - {str(e)}")
                self.report_script_result(
                    script_hash=script_hash,
                    exit_code=127,
                    stdout="",
                    stderr=str(e),
                    duration_ms=0
                )
    
    def report_script_result(self, script_hash: str, exit_code: int, stdout: str, 
                            stderr: str, duration_ms: int):
        """Report script result back to backend."""
        try:
            payload = {
                'job_id': self.job_id,
                'script_hash': script_hash,
                'exit_code': exit_code,
                'stdout': stdout[:5000],  # Limit size
                'stderr': stderr[:5000],
                'duration_ms': duration_ms
            }
            
            response = requests.post(
                f"{self.backend_url}/agent/script_result",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.log(f"Reported script result: {script_hash[:8]}")
            else:
                self.log(f"Failed to report script result: {response.status_code}")
        
        except Exception as e:
            self.log(f"Error reporting script result: {str(e)}")
    
    async def run(self):
        """Main agent loop."""
        try:
            self.log("Agent starting...")
            
            # Clone repository
            if not self.clone_repo():
                self.log("Failed to clone repository, exiting")
                return
            
            # Run scripts (Phase 1)
            self.run_scripts()
            
            # TODO: Phase 2 - Agent loop with Claude decision-making
            # for now, just complete
            self.log("Agent completed")
        
        except Exception as e:
            self.log(f"Agent error: {str(e)}")


def main():
    """Main entry point."""
    try:
        agent = Agent()
        
        # Run agent
        import asyncio
        asyncio.run(agent.run())
    
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
