"""Unit tests for database models"""

import pytest

from models.database import (
    Event,
    Job,
    PaperAnalysis,
    User,
)

pytestmark = [pytest.mark.unit, pytest.mark.db]


class TestUserModel:
    """Test User model"""

    def test_user_fields(self):
        """Test User model has required fields"""
        assert hasattr(User, "username")
        assert hasattr(User, "password_hash")
        assert hasattr(User, "email")
        assert hasattr(User, "is_active")
        assert hasattr(User, "created_at")


class TestJobModel:
    """Test Job model"""

    def test_job_fields(self):
        """Test Job model has required fields"""
        assert hasattr(Job, "user")
        assert hasattr(Job, "status")
        assert hasattr(Job, "current_stage")
        assert hasattr(Job, "progress")
        assert hasattr(Job, "pdf_path")
        assert hasattr(Job, "created_at")


class TestPaperAnalysisModel:
    """Test PaperAnalysis model"""

    def test_paper_analysis_json_fields(self):
        """Test PaperAnalysis handles JSON fields"""
        assert hasattr(PaperAnalysis, "citations")  # JSON field
        assert hasattr(PaperAnalysis, "title")
        assert hasattr(PaperAnalysis, "abstract")


class TestEventModel:
    """Test Event model"""

    def test_event_fields(self):
        """Test Event model has required fields"""
        # Check fields exist on the model class (not instance to avoid FK issues)
        assert hasattr(Event, "job")
        assert hasattr(Event, "step")
        assert hasattr(Event, "message")
        assert hasattr(Event, "severity")
        assert hasattr(Event, "stage_duration_ms")
        assert hasattr(Event, "timestamp")
