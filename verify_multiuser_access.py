#!/usr/bin/env python3
"""
Manual verification script for multi-user access control changes.
Checks that the changes to app.py enforce user isolation.
"""

import re

def check_function_has_decorator(filepath, function_name):
    """Check if a function has @require_auth decorator."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the function definition and check previous lines
    pattern = rf'def {function_name}\('
    match = re.search(pattern, content)
    
    if not match:
        return False, f"Function {function_name} not found"
    
    # Get the 10 lines before the function
    lines_before_match = content[:match.start()].split('\n')[-10:]
    text_before = '\n'.join(lines_before_match)
    
    if '@require_auth' in text_before:
        return True, f"✓ {function_name} has @require_auth"
    else:
        return False, f"✗ {function_name} missing @require_auth"

def check_function_has_code(filepath, function_name, search_code):
    """Check if a function contains specific code."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find function
    pattern = rf'def {function_name}\(.*?\):'
    match = re.search(pattern, content)
    
    if not match:
        return False, f"Function {function_name} not found"
    
    # Get function body (next 3000 chars)
    func_start = match.end()
    func_body = content[func_start:func_start+3000]
    
    if search_code in func_body:
        return True, f"✓ {function_name} has '{search_code}'"
    else:
        return False, f"✗ {function_name} missing '{search_code}'"

def check_route_methods(filepath, route_path):
    """Check if route supports both GET and POST."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the route with /logout
    pattern = rf'@app\.route\("{route_path}".*?\)'
    match = re.search(pattern, content)
    
    if not match:
        return False, f"Route {route_path} not found"
    
    route_str = match.group(0)
    
    supports_get = 'GET' in route_str or 'methods=' not in route_str
    supports_post = 'POST' in route_str
    
    if supports_get and supports_post:
        return True, f"✓ {route_path} handles both GET and POST"
    else:
        methods = []
        if supports_get:
            methods.append('GET')
        if supports_post:
            methods.append('POST')
        return False, f"✗ {route_path} only handles: {', '.join(methods)}"

def main():
    """Run all verification checks."""
    filepath = '/home/user/.openclaw/workspace/paper-reproducibility/app.py'
    
    print("=" * 70)
    print("MULTI-USER ACCESS CONTROL VERIFICATION")
    print("=" * 70)
    print()
    
    checks = [
        # Core auth checks
        ("GET /logout endpoint (both GET and POST)", lambda: check_route_methods(filepath, "/logout")),
        
        # Protected routes - decorators
        ("GET /jobs has @require_auth", lambda: check_function_has_decorator(filepath, 'list_jobs')),
        ("GET /job/<id> has @require_auth", lambda: check_function_has_decorator(filepath, 'get_job')),
        ("GET /api/job/<id>/full has @require_auth", lambda: check_function_has_decorator(filepath, 'get_job_full')),
        ("POST /upload has @require_auth", lambda: check_function_has_decorator(filepath, 'upload_pdf')),
        ("GET /events/<id> has @require_auth", lambda: check_function_has_decorator(filepath, 'events')),
        ("DELETE /job/<id> has @require_auth", lambda: check_function_has_decorator(filepath, 'delete_job')),
        ("POST /api/job/<id>/chat has @require_auth", lambda: check_function_has_decorator(filepath, 'chat_with_paper')),
        ("GET /api/job/<id>/chat/history has @require_auth", lambda: check_function_has_decorator(filepath, 'get_chat_history_endpoint')),
        ("DELETE /api/job/<id>/chat/history has @require_auth", lambda: check_function_has_decorator(filepath, 'delete_chat_history')),
        
        # User isolation checks
        ("GET /jobs filters by user_id", lambda: check_function_has_code(filepath, 'list_jobs', 'WHERE j.user_id = ?')),
        ("GET /job/<id> verifies ownership", lambda: check_function_has_code(filepath, 'get_job', 'job["user_id"] != user_id')),
        ("GET /api/job/<id>/full verifies ownership", lambda: check_function_has_code(filepath, 'get_job_full', 'job["user_id"] != user_id')),
        ("POST /api/job/<id>/chat verifies ownership", lambda: check_function_has_code(filepath, 'chat_with_paper', 'job["user_id"] != user_id')),
        ("GET /api/job/<id>/chat/history verifies ownership", lambda: check_function_has_code(filepath, 'get_chat_history_endpoint', 'job["user_id"] != user_id')),
        ("DELETE /api/job/<id>/chat/history verifies ownership", lambda: check_function_has_code(filepath, 'delete_chat_history', 'job["user_id"] != user_id')),
        ("DELETE /job/<id> verifies ownership", lambda: check_function_has_code(filepath, 'delete_job', 'job["user_id"] != user_id')),
        ("GET /events/<id> verifies ownership", lambda: check_function_has_code(filepath, 'events', 'job["user_id"] != user_id')),
        
        # Logout functionality
        ("POST /logout redirects to login", lambda: check_function_has_code(filepath, 'logout', 'redirect("/login")')),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            passed, message = check_func()
            results.append((check_name, passed))
            status = "✓" if passed else "✗"
            print(f"{status} {message}")
        except Exception as e:
            results.append((check_name, False))
            print(f"✗ {check_name}: {str(e)}")
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()
    
    if passed == total:
        print("✓✓✓ All checks passed! Multi-user access control is properly implemented. ✓✓✓")
        return 0
    else:
        print("✗ Some checks failed. Please review the errors above.")
        failed_checks = [name for name, p in results if not p]
        print("\nFailed checks:")
        for name in failed_checks:
            print(f"  - {name}")
        return 1

if __name__ == '__main__':
    exit(main())
