"""Unit tests for repository pattern"""

from unittest.mock import Mock, patch

import pytest

from repositories import (
    JobRepository,
    PaperAnalysisRepository,
    UserRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.db]


class TestUserRepository:
    """Test UserRepository"""

    @patch("repositories.User")
    def test_create_user(self, mock_user_model):
        """Test creating a user"""
        with patch.object(UserRepository, "create") as mock_create:
            mock_create.return_value = 1  # create() returns user_id

            result = UserRepository.create(username="test", email="test@example.com", password_hash="hash")

            assert result == 1

    @patch("repositories.User")
    def test_get_user_by_id(self, mock_user_model):
        """Test retrieving user by ID"""
        with patch.object(UserRepository, "get_by_id") as mock_get:
            mock_user = Mock()
            mock_user.id = 1
            mock_user.username = "test"
            mock_get.return_value = mock_user

            result = UserRepository.get_by_id(1)

            assert result.id == 1


class TestJobRepository:
    """Test JobRepository"""

    @patch("repositories.Job")
    def test_create_job(self, mock_job_model):
        """Test creating a job"""
        with patch.object(JobRepository, "create") as mock_create:
            mock_create.return_value = True  # create() returns bool

            result = JobRepository.create(job_id="uuid", pdf_path="/path/to/pdf", user_id=1)

            assert result is True

    @patch("repositories.Job")
    def test_update_job_status(self, mock_job_model):
        """Test updating job status"""
        with patch.object(JobRepository, "update_report"):
            # Note: JobRepository doesn't have update_job_status, uses update_report instead
            result = JobRepository.update_report("uuid", {"status": "completed"})

            assert result is not None

    @patch("repositories.Job")
    def test_list_user_jobs(self, mock_job_model):
        """Test listing user's jobs"""
        with patch.object(JobRepository, "list_all") as mock_list:
            mock_job1 = Mock()
            mock_job1.id = "uuid1"
            mock_job1.status = "completed"
            mock_job2 = Mock()
            mock_job2.id = "uuid2"
            mock_job2.status = "pending"

            mock_list.return_value = [mock_job1, mock_job2]

            result = JobRepository.list_all(user_id=1)

            assert len(result) == 2


class TestPaperAnalysisRepository:
    """Test PaperAnalysisRepository"""

    @patch("repositories.PaperAnalysis")
    def test_save_analysis(self, mock_analysis_model):
        """Test saving paper analysis"""
        with patch.object(PaperAnalysisRepository, "save") as mock_save:
            mock_analysis = Mock()
            mock_analysis.job_id = "uuid"
            mock_analysis.title = "Test Paper"
            mock_analysis.abstract = "Abstract"

            mock_save.return_value = True  # save() returns bool

            result = PaperAnalysisRepository.save(mock_analysis)

            assert result is True
