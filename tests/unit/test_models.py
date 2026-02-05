"""Unit tests for database models"""

import pytest
from models.database import (
    User, Job, PaperAnalysis, ExecutionDetails, 
    AspectEvaluation, Event, ChatSession, ChatMessage
)

pytestmark = [pytest.mark.unit, pytest.mark.db]

class TestUserModel:
    """Test User model"""
    
    def test_user_fields(self):
        """Test User model has required fields"""
        user = User()
        assert hasattr(user, 'username')
        assert hasattr(user, 'password_hash')
        assert hasattr(user, 'is_active')
        assert hasattr(user, 'is_admin')
        assert hasattr(user, 'created_at')

class TestJobModel:
    """Test Job model"""
    
    def test_job_fields(self):
        """Test Job model has required fields"""
        job = Job()
        assert hasattr(job, 'user_id')
        assert hasattr(job, 'status')
        assert hasattr(job, 'current_stage')
        assert hasattr(job, 'progress')
        assert hasattr(job, 'pdf_path')
        assert hasattr(job, 'created_at')

class TestPaperAnalysisModel:
    """Test PaperAnalysis model"""
    
    def test_paper_analysis_json_fields(self):
        """Test PaperAnalysis handles JSON fields"""
        analysis = PaperAnalysis()
        assert hasattr(analysis, 'citations')  # JSON field
        assert hasattr(analysis, 'title')
        assert hasattr(analysis, 'abstract')

class TestEventModel:
    """Test Event model"""
    
    def test_event_fields(self):
        """Test Event model has required fields"""
        event = Event()
        assert hasattr(event, 'job_id')
        assert hasattr(event, 'step')
        assert hasattr(event, 'message')
        assert hasattr(event, 'severity')
        assert hasattr(event, 'progress')
        assert hasattr(event, 'timestamp')
