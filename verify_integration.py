#!/usr/bin/env python3
"""Verify aspect plugin integration."""

import sys
import traceback

def test_imports():
    """Test all necessary imports."""
    try:
        from services.plugin_service import PluginService
        print("✅ PluginService imported")
        
        from services.evaluation_service import evaluate_paper
        print("✅ evaluate_paper imported")
        
        from services.pipeline_orchestrator import stage_3_evaluation
        print("✅ stage_3_evaluation imported")
        
        from repositories import AspectRepository, UserPluginRepository
        print("✅ Repositories imported")
        
        from models.plugin import Plugin, UserPlugin
        print("✅ Plugin models imported")
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_stage_3_function():
    """Test that stage_3_evaluation function exists and is callable."""
    try:
        from services.pipeline_orchestrator import stage_3_evaluation
        
        # Check it's callable
        if not callable(stage_3_evaluation):
            print("❌ stage_3_evaluation is not callable")
            return False
        
        print("✅ stage_3_evaluation is callable")
        return True
    except Exception as e:
        print(f"❌ Error testing stage_3_evaluation: {e}")
        traceback.print_exc()
        return False

def test_aspect_service_methods():
    """Test PluginService has required methods."""
    try:
        from services.plugin_service import PluginService
        
        required_methods = [
            'get_or_create_default_aspects',
            'get_all_aspects_for_user',
            'get_active_aspects_for_evaluation',
            'create_custom_aspect',
            'activate_aspect',
            'deactivate_aspect'
        ]
        
        for method in required_methods:
            if not hasattr(PluginService, method):
                print(f"❌ PluginService missing method: {method}")
                return False
        
        print(f"✅ PluginService has all {len(required_methods)} required methods")
        return True
    except Exception as e:
        print(f"❌ Error testing PluginService: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("ASPECT PLUGIN INTEGRATION VERIFICATION")
    print("=" * 60)
    print()
    
    results = []
    
    print("1. Testing imports...")
    results.append(test_imports())
    print()
    
    print("2. Testing stage_3_evaluation function...")
    results.append(test_stage_3_function())
    print()
    
    print("3. Testing PluginService methods...")
    results.append(test_aspect_service_methods())
    print()
    
    print("=" * 60)
    if all(results):
        print("✅ ALL VERIFICATIONS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
