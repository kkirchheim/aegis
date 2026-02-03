"""
Pytest configuration and fixtures for Paper Reproducibility Checker tests.

This conftest.py:
1. Adds the parent directory to sys.path so 'app' and 'agent' modules can be imported
2. Sets a dummy ANTHROPIC_API_KEY for tests (prevents import-time errors)
3. Works in both Docker and CI environments without requiring real API credentials
"""

import sys
import os

# Set dummy API key for testing to avoid import-time errors
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-key-for-pytest"

# Add parent directory to path so 'app' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
