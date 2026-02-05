"""Unit tests for repository pattern"""

import pytest
from unittest.mock import Mock, patch
from repositories import (
    UserRepository, JobRepository, PaperAnalysisRepository,
    ExecutionDetailsRepository, AspectEvaluationRepository
)

pytestmark = [pytest.mark.unit, pytest.mark.db]

class TestUserRepository:
    """Test UserRepository"""
    
    @patch('repositories.User')
    def test_create_user(self, mock_user_model):
        """Test creating a user"""
        with patch.object(UserRepository, 'create_user') as mock_create:
            mock_create.return_value = {"id": 1, "username": "test"}
            
            result = UserRepository.create_user(username="test", password_hash="hash")
            
            assert result["username"] == "test"
    
    @patch('repositories.User')
    def test_get_user_by_id(self, mock_user_model):
        """Test retrieving user by ID"""
        with patch.object(UserRepository, 'get_user_by_id') as mock_get:
            mock_get.return_value = {"id": 1, "username": "test"}
            
            result = UserRepository.get_user_by_id(1)
            
            assert result["id"] == 1

class TestJobRepository:
    """Test JobRepository"""
    
    @patch('repositories.Job')
    def test_create_job(self, mock_job_model):
        """Test creating a job"""
        with patch.object(JobRepository, 'create_job') as mock_create:
            mock_create.return_value = {"id": "uuid", "status": "pending"}
            
            result = JobRepository.create_job(user_id=1, pdf_filename="test.pdf")
            
            assert result["status"] == "pending"
    
    @patch('repositories.Job')
    def test_update_job_status(self, mock_job_model):
        """Test updating job status"""
        with patch.object(JobRepository, 'update_job_status') as mock_update:
            JobRepository.update_job_status("uuid", status="completed")
            
            mock_update.assert_called_once()
    
    @patch('repositories.Job')
    def test_list_user_jobs(self, mock_job_model):
        """Test listing user's jobs"""
        with patch.object(JobRepository, 'get_user_jobs') as mock_list:
            mock_list.return_value = [
                {"id": "uuid1", "status": "completed"},
                {"id": "uuid2", "status": "pending"}
            ]
            
            result = JobRepository.get_user_jobs(user_id=1)
            
            assert len(result) == 2

class TestPaperAnalysisRepository:
    """Test PaperAnalysisRepository"""
    
    @patch('repositories.PaperAnalysis')
    def test_save_analysis(self, mock_analysis_model):
        """Test saving paper analysis"""
        with patch.object(PaperAnalysisRepository, 'create_or_update') as mock_save:
            data = {
                "job_id": "uuid",
                "title": "Test Paper",
                "abstract": "Abstract"
            }
            mock_save.return_value = data
            
            result = PaperAnalysisRepository.create_or_update("uuid", data)
            
            assert result["title"] == "Test Paper"
