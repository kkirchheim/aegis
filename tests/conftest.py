"""
Pytest configuration and fixtures for Paper Reproducibility Checker tests.

This conftest.py adds the parent directory to sys.path so that imports of 'app' and 'agent'
work correctly in both Docker and CI environments.
"""

import sys
import os

# Add parent directory to path so 'app' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
