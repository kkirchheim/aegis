#!/usr/bin/env python3
"""
Test to verify that cache functions are properly guarded in app.py.
This test checks the source code without importing the module.
"""

import os
import re

def test_cache_implementation():
    """Verify cache functions are properly wrapped with ENABLE_CACHING checks."""
    
    print("=" * 60)
    print("Verifying Cache Implementation")
    print("=" * 60)
    
    # Read the app.py file
    with open('app.py', 'r') as f:
        app_code = f.read()
    
    # Test 1: Check that ENABLE_CACHING is configured
    print("\n[Test 1] ENABLE_CACHING configuration exists")
    if "ENABLE_CACHING = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'" in app_code:
        print("✓ ENABLE_CACHING config found at module level")
    else:
        print("✗ ENABLE_CACHING config not found")
        return False
    
    # Test 2: Check that all cache functions have the guard
    print("\n[Test 2] All cache functions are properly guarded")
    
    functions_to_check = [
        ('get_cached_paper_analysis', 'get_cached_paper_analysis'),
        ('store_paper_analysis_cache', 'store_paper_analysis_cache'),
        ('get_cached_evaluation', 'get_cached_evaluation'),
        ('store_evaluation_cache', 'store_evaluation_cache'),
    ]
    
    for func_name, func_pattern in functions_to_check:
        # Find function definition
        pattern = f"def {func_pattern}\\("
        match = re.search(pattern, app_code)
        
        if not match:
            print(f"✗ Function {func_name}() not found")
            return False
        
        # Get the function body
        start_pos = match.start()
        # Find the next function definition or end of file
        next_func = re.search(r"\ndef ", app_code[start_pos + 1:])
        if next_func:
            func_body = app_code[start_pos:start_pos + next_func.start() + 1]
        else:
            func_body = app_code[start_pos:]
        
        # Check for the guard
        if "if not ENABLE_CACHING:" in func_body:
            print(f"✓ {func_name}() has ENABLE_CACHING guard")
        else:
            print(f"✗ {func_name}() missing ENABLE_CACHING guard")
            return False
    
    # Test 3: Verify cache calls are made in the right places
    print("\n[Test 3] Cache functions are called in analysis pipeline")
    
    cache_calls = [
        ('get_cached_paper_analysis(pdf_hash)', 'Paper analysis cache read'),
        ('store_paper_analysis_cache(pdf_hash', 'Paper analysis cache write'),
        ('get_cached_evaluation(paper_hash', 'Evaluation cache read'),
        ('store_evaluation_cache(paper_hash', 'Evaluation cache write'),
    ]
    
    for call_pattern, desc in cache_calls:
        if call_pattern in app_code:
            print(f"✓ {desc} found")
        else:
            print(f"✗ {desc} not found")
            return False
    
    # Test 4: Check .env file
    print("\n[Test 4] .env file contains ENABLE_CACHING configuration")
    with open('.env', 'r') as f:
        env_content = f.read()
    
    if 'ENABLE_CACHING=false' in env_content:
        print("✓ ENABLE_CACHING=false in .env (disabled by default)")
    else:
        print("✗ ENABLE_CACHING not found in .env or not set to false")
        return False
    
    # Test 5: Check README documentation
    print("\n[Test 5] README documents caching configuration")
    with open('README.md', 'r') as f:
        readme = f.read()
    
    checks = [
        ('Caching Configuration', 'Section title'),
        ('caching is disabled', 'Default behavior'),
        ('export ENABLE_CACHING=true', 'Enable instruction'),
        ('Cache behavior:', 'Behavior documentation'),
    ]
    
    for pattern, desc in checks:
        if pattern in readme:
            print(f"✓ {desc} documented")
        else:
            print(f"✗ {desc} not documented")
            return False
    
    print("\n" + "=" * 60)
    print("All implementation tests passed! ✓")
    print("=" * 60)
    
    print("\n[Implementation Summary]")
    print("✓ ENABLE_CACHING configuration added to app.py")
    print("✓ All 4 cache functions properly guarded")
    print("✓ Caching disabled by default in .env")
    print("✓ README documents the configuration")
    print("✓ Cache calls in correct pipeline locations")
    
    return True

if __name__ == "__main__":
    import sys
    try:
        success = test_cache_implementation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
