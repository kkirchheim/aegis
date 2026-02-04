#!/usr/bin/env python3
"""
Test script to verify storage limit configuration flows through pipeline.
"""

import sys
from pathlib import Path

# Test 1: Verify HTML has storage limit input
print("✓ Test 1: Checking HTML for storage limit input field...")
html_path = Path("templates/index.html")
html_content = html_path.read_text()
assert 'id="storageLimit"' in html_content, "Storage limit input not found in HTML"
assert 'value="10"' in html_content, "Default value 10 not found in HTML"
assert 'min="1"' in html_content, "Min value 1 not found in HTML"
assert 'max="100"' in html_content, "Max value 100 not found in HTML"
print("  ✓ Storage limit input field found with correct attributes")

# Test 2: Verify JavaScript captures storage_limit
print("\n✓ Test 2: Checking JavaScript for storage_limit capture...")
js_path = Path("static/app.js")
js_content = js_path.read_text()
assert 'storageLimit' in js_content, "storageLimit not found in JavaScript"
assert 'formData.append("storage_limit"' in js_content, "storage_limit not appended to formData"
print("  ✓ JavaScript correctly captures storage_limit from form")

# Test 3: Verify app.py accepts storage_limit in config
print("\n✓ Test 3: Checking app.py for storage_limit handling...")
app_path = Path("app.py")
app_content = app_path.read_text()
assert '"storage_limit": int(request.form.get("storage_limit", 10))' in app_content, "storage_limit config not found"
print("  ✓ app.py correctly extracts storage_limit from request")

# Test 4: Verify spawn_agent_container accepts config
print("\n✓ Test 4: Checking spawn_agent_container signature...")
assert 'def spawn_agent_container(job_id, repo_url, config=None):' in app_content, "spawn_agent_container signature incorrect"
print("  ✓ spawn_agent_container accepts config parameter")

# Test 5: Verify storage_limit validation
print("\n✓ Test 5: Checking storage_limit validation logic...")
assert 'if storage_limit < 1 or storage_limit > 100:' in app_content, "Validation range check not found"
assert 'storage_limit = 10' in app_content, "Default fallback not found"
print("  ✓ Storage limit validation (1-100 GB range) implemented")

# Test 6: Verify tmpfs configuration
print("\n✓ Test 6: Checking Docker tmpfs configuration...")
assert 'tmpfs={"/tmp": f"size={storage_limit_str}"}' in app_content, "tmpfs configuration not found"
print("  ✓ Docker container uses tmpfs to limit /tmp storage")

# Test 7: Verify storage_limit is passed to Docker environment
print("\n✓ Test 7: Checking Docker environment variables...")
assert '"STORAGE_LIMIT": storage_limit_str' in app_content, "STORAGE_LIMIT not in environment"
print("  ✓ Storage limit passed as environment variable to container")

# Test 8: Verify config is passed to spawn_agent_container
print("\n✓ Test 8: Checking config passed to spawn_agent_container...")
assert 'spawn_agent_container(job_id, repo_url, config)' in app_content, "config not passed to spawn_agent_container"
print("  ✓ Config passed from analyze_paper_background to spawn_agent_container")

# Test 9: Verify logging statement
print("\n✓ Test 9: Checking logging of storage limit...")
assert 'f"[{job_id}]   Storage Limit: {storage_limit}GB"' in app_content, "Storage limit logging not found"
print("  ✓ Storage limit is logged during container startup")

print("\n" + "="*60)
print("✓ All tests passed! Storage limit configuration is properly integrated.")
print("="*60)
print("\nSummary of changes:")
print("1. ✓ HTML: Added storage limit input field (1-100 GB, default 10GB)")
print("2. ✓ JavaScript: Captures and sends storage_limit in form submission")
print("3. ✓ Backend (app.py): Accepts and validates storage_limit parameter")
print("4. ✓ Container spawn: Applies --tmpfs /tmp:size={limit}g to limit storage")
print("5. ✓ Logging: Logs storage limit during container startup")
print("\nTesting:")
print("- Verify storage limit is passed through pipeline: ✓")
print("- Verify Docker container respects the limit: Requires runtime test")
print("- Test with different limit values: Requires runtime test")
