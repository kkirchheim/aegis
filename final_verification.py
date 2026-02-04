#!/usr/bin/env python3
"""Final verification that storage limit configuration is complete."""

import re
from pathlib import Path

def check_file_has_pattern(filepath, pattern, description):
    """Check if file contains expected pattern."""
    content = Path(filepath).read_text()
    if re.search(pattern, content, re.DOTALL | re.MULTILINE):
        print(f"  ✓ {description}")
        return True
    else:
        print(f"  ✗ {description}")
        return False

def main():
    print("="*70)
    print("FINAL VERIFICATION: Storage Limit Configuration")
    print("="*70)
    
    checks = []
    
    # HTML checks
    print("\n1. HTML (templates/index.html)")
    checks.append(check_file_has_pattern(
        "templates/index.html",
        r'id="storageLimit".*?value="10".*?min="1".*?max="100"',
        "Storage limit input field with correct attributes"
    ))
    checks.append(check_file_has_pattern(
        "templates/index.html",
        r"Storage Limit \(GB\)",
        "Storage limit label"
    ))
    
    # JavaScript checks
    print("\n2. JavaScript (static/app.js)")
    checks.append(check_file_has_pattern(
        "static/app.js",
        r'formData\.append\("storage_limit"',
        "storage_limit appended to formData"
    ))
    checks.append(check_file_has_pattern(
        "static/app.js",
        r'document\.getElementById\("storageLimit"\)\.value',
        "storageLimit input value captured"
    ))
    
    # Backend checks
    print("\n3. Backend (app.py - /upload endpoint)")
    checks.append(check_file_has_pattern(
        "app.py",
        r'"storage_limit":\s*int\(request\.form\.get\("storage_limit",\s*10\)\)',
        "storage_limit extracted from form with default 10"
    ))
    
    print("\n4. Backend (app.py - analyze_paper_background)")
    checks.append(check_file_has_pattern(
        "app.py",
        r'spawn_agent_container\(job_id,\s*repo_url,\s*config\)',
        "config passed to spawn_agent_container"
    ))
    
    print("\n5. Backend (app.py - spawn_agent_container)")
    checks.append(check_file_has_pattern(
        "app.py",
        r'def spawn_agent_container\(job_id,\s*repo_url,\s*config=None\)',
        "spawn_agent_container accepts config parameter"
    ))
    checks.append(check_file_has_pattern(
        "app.py",
        r'if\s+storage_limit\s+<\s+1\s+or\s+storage_limit\s+>\s+100',
        "storage_limit validation (1-100 range)"
    ))
    checks.append(check_file_has_pattern(
        "app.py",
        r'tmpfs=\{"/tmp":\s*f"size={storage_limit_str}"\}',
        "tmpfs parameter for Docker container"
    ))
    checks.append(check_file_has_pattern(
        "app.py",
        r'"STORAGE_LIMIT":\s*storage_limit_str',
        "STORAGE_LIMIT environment variable"
    ))
    checks.append(check_file_has_pattern(
        "app.py",
        r'f"\[{job_id}\]\s+Storage Limit:.*GB"',
        "Storage limit logging"
    ))
    
    # Summary
    print("\n" + "="*70)
    total_checks = len(checks)
    passed_checks = sum(checks)
    
    if all(checks):
        print(f"✓ ALL CHECKS PASSED ({passed_checks}/{total_checks})")
        print("\nStorage limit configuration is complete and properly integrated!")
        print("\nConfiguration pipeline:")
        print("  User Input → HTML form")
        print("             → JavaScript capture")
        print("             → POST /upload request")
        print("             → Backend validation")
        print("             → Config dict")
        print("             → analyze_paper_background()")
        print("             → spawn_agent_container()")
        print("             → Docker --tmpfs limit")
        return 0
    else:
        print(f"✗ SOME CHECKS FAILED ({passed_checks}/{total_checks})")
        return 1

if __name__ == "__main__":
    exit(main())
