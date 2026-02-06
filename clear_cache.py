#!/usr/bin/env python3
"""Clear evaluation cache."""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models.database import CacheEvaluation, CacheCodeExecution, CachePaperAnalysis

with app.app_context():
    # Clear all caches
    deleted_eval = CacheEvaluation.delete().execute()
    deleted_code = CacheCodeExecution.delete().execute()
    deleted_paper = CachePaperAnalysis.delete().execute()
    
    print(f"✓ Cleared evaluation cache: {deleted_eval} evals, {deleted_code} code, {deleted_paper} papers")
