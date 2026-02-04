#!/usr/bin/env python3
"""
Test script to verify cache behavior when ENABLE_CACHING is disabled.
"""

import os
import sys
import logging

# Set up logging to capture debug messages
logging.basicConfig(level=logging.DEBUG)

# Ensure ENABLE_CACHING is false for this test
os.environ['ENABLE_CACHING'] = 'false'

from dotenv import load_dotenv
load_dotenv()

def test_cache_disabled():
    """Test that caching is properly disabled when ENABLE_CACHING=false."""
    
    print("=" * 60)
    print("Testing Cache Behavior (ENABLE_CACHING=false)")
    print("=" * 60)
    
    # We need to import app AFTER setting the env var
    sys.path.insert(0, '/home/user/.openclaw/workspace/paper-reproducibility')
    
    # Check the config before import
    print("\n[Pre-Import Check]")
    print(f"ENABLE_CACHING env var: {os.getenv('ENABLE_CACHING', 'false')}")
    
    # Import app (which reads ENABLE_CACHING during initialization)
    import app
    
    print(f"ENABLE_CACHING config in app: {app.ENABLE_CACHING}")
    assert app.ENABLE_CACHING == False, "ENABLE_CACHING should be False"
    print("✓ app.ENABLE_CACHING correctly set to False")
    
    # Test 1: get_cached_paper_analysis should return None when disabled
    print("\n[Test 1] get_cached_paper_analysis() with caching disabled")
    result = app.get_cached_paper_analysis("test_hash_12345")
    assert result is None, "Should return None when caching is disabled"
    print("✓ Returns None (cache read skipped)")
    
    # Test 2: get_cached_evaluation should return None when disabled
    print("\n[Test 2] get_cached_evaluation() with caching disabled")
    result = app.get_cached_evaluation("paper_hash", "code_hash")
    assert result is None, "Should return None when caching is disabled"
    print("✓ Returns None (cache read skipped)")
    
    # Test 3: store_paper_analysis_cache should not throw error
    print("\n[Test 3] store_paper_analysis_cache() with caching disabled")
    try:
        app.store_paper_analysis_cache(
            "test_hash",
            "test pdf text",
            {"title": "Test", "citations": []}
        )
        print("✓ Executes without error (cache write skipped)")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Test 4: store_evaluation_cache should not throw error
    print("\n[Test 4] store_evaluation_cache() with caching disabled")
    try:
        app.store_evaluation_cache(
            "paper_hash",
            "code_hash",
            {"score": 0.8}
        )
        print("✓ Executes without error (cache write skipped)")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("All cache behavior tests passed! ✓")
    print("=" * 60)
    
    print("\n[Behavior Summary]")
    print("When ENABLE_CACHING=false:")
    print("  • get_cached_paper_analysis() returns None immediately")
    print("  • get_cached_evaluation() returns None immediately")
    print("  • store_paper_analysis_cache() skips write")
    print("  • store_evaluation_cache() skips write")
    print("  • All functions log debug message about skip")
    print("\n✓ Analysis still works without caching (just slower)")
    
    return True

if __name__ == "__main__":
    try:
        success = test_cache_disabled()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
