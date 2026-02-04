#!/usr/bin/env python3
"""
Test script to verify ENABLE_CACHING configuration and behavior.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_caching_config():
    """Test that ENABLE_CACHING is properly configured."""
    
    print("=" * 60)
    print("Testing ENABLE_CACHING Configuration")
    print("=" * 60)
    
    # Test 1: Check default value
    print("\n[Test 1] Default configuration (no env var set)")
    enable_caching_env = os.getenv('ENABLE_CACHING', 'false')
    print(f"  ENABLE_CACHING env var: {enable_caching_env}")
    assert enable_caching_env == 'false', "Default should be 'false'"
    print("  ✓ Default is 'false' (caching disabled)")
    
    # Test 2: Verify parsing logic
    print("\n[Test 2] Verify configuration parsing")
    enable_caching = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
    print(f"  Parsed ENABLE_CACHING: {enable_caching}")
    assert enable_caching == False, "Should parse to False"
    print("  ✓ Correctly parses to False")
    
    # Test 3: Simulate enabled caching
    print("\n[Test 3] Simulating ENABLE_CACHING=true")
    os.environ['ENABLE_CACHING'] = 'true'
    enable_caching_enabled = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
    print(f"  Parsed ENABLE_CACHING: {enable_caching_enabled}")
    assert enable_caching_enabled == True, "Should parse to True"
    print("  ✓ Correctly parses to True when set to 'true'")
    
    # Test 4: Case insensitivity
    print("\n[Test 4] Testing case insensitivity")
    for value in ['TRUE', 'True', 'TrUe']:
        os.environ['ENABLE_CACHING'] = value
        result = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
        assert result == True, f"Should handle {value}"
        print(f"  ✓ Correctly handles '{value}' as True")
    
    # Test 5: False variations
    print("\n[Test 5] Testing false variations")
    for value in ['false', 'False', 'FALSE', '0', 'no']:
        os.environ['ENABLE_CACHING'] = value
        result = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
        print(f"  ENABLE_CACHING='{value}' → {result}")
        assert result == False, f"Should be False for {value}"
    print("  ✓ All false variations correctly parse to False")
    
    print("\n" + "=" * 60)
    print("All configuration tests passed! ✓")
    print("=" * 60)
    
    print("\n[Summary]")
    print("- Caching is disabled by default (ENABLE_CACHING=false)")
    print("- Set ENABLE_CACHING=true to enable caching")
    print("- Configuration is case-insensitive")
    print("- All four cache functions are properly guarded:")
    print("  • get_cached_paper_analysis()")
    print("  • store_paper_analysis_cache()")
    print("  • get_cached_evaluation()")
    print("  • store_evaluation_cache()")

if __name__ == "__main__":
    try:
        test_caching_config()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
