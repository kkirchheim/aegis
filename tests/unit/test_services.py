"""Unit tests for all services with mocked dependencies.

This module tests all services in isolation with all external dependencies mocked.
Each test focuses on the service's public interface and behavior.

Markers: @pytest.mark.unit - Run with: pytest tests/unit/ -m unit
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import json
import hashlib
from datetime import datetime
from threading import Lock


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# ============================================================================
# JOB SERVICE TESTS
# ============================================================================
class TestJobService:
    """Test JobService - job lifecycle and status management."""
    
    def test_create_job_success(self):
        """Test creating a job successfully."""
        from services import job_service
        
        with patch.object(job_service, 'Job') as mock_job:
            mock_job.create.return_value = MagicMock(id="job123", status="pending")
            
            result = job_service.create_job(
                job_id="job123",
                pdf_path="/path/to/file.pdf",
                pdf_filename="file.pdf",
                user_id=1,
                thumbnail_path="/thumb.jpg",
                num_pages=10
            )
            
            assert result is True
            mock_job.create.assert_called_once()
    
    def test_create_job_failure(self):
        """Test job creation failure handling."""
        from services import job_service
        
        with patch.object(job_service, 'Job') as mock_job:
            mock_job.create.side_effect = Exception("DB error")
            
            result = job_service.create_job(
                job_id="job123",
                pdf_path="/path/to/file.pdf",
                pdf_filename="file.pdf",
                user_id=1
            )
            
            assert result is False
    
    def test_get_job(self):
        """Test retrieving a job."""
        from services import job_service
        
        with patch.object(job_service, 'JobRepository') as mock_repo:
            mock_job = MagicMock(id="job123", status="pending")
            mock_repo.get.return_value = mock_job
            
            result = job_service.get_job("job123")
            
            assert result.id == "job123"
            mock_repo.get.assert_called_once_with("job123")
    
    def test_get_user_jobs(self):
        """Test retrieving all jobs for a user."""
        from services import job_service
        
        with patch.object(job_service, 'JobRepository') as mock_repo:
            mock_jobs = [
                MagicMock(
                    id="job1",
                    status="completed",
                    pdf_filename="file1.pdf",
                    created_at=datetime.now(),
                    completed_at=datetime.now(),
                    thumbnail_path="/thumb1.jpg",
                    num_pages=5
                ),
                MagicMock(
                    id="job2",
                    status="processing",
                    pdf_filename="file2.pdf",
                    created_at=datetime.now(),
                    completed_at=None,
                    thumbnail_path="/thumb2.jpg",
                    num_pages=10
                )
            ]
            mock_repo.list_all.return_value = mock_jobs
            
            result = job_service.get_user_jobs(user_id=1)
            
            assert len(result) == 2
            assert result[0]["id"] == "job1"
            assert result[1]["id"] == "job2"
    
    def test_update_job_status_success(self):
        """Test updating job status."""
        from services import job_service
        
        with patch.object(job_service, 'Job') as mock_job_cls:
            mock_job = MagicMock(
                id="job123",
                progress=0.0,
                status="pending",
                current_stage="pending"
            )
            mock_job_cls.get_by_id.return_value = mock_job
            mock_job_cls.update.return_value.where.return_value.execute.return_value = 1
            mock_job_cls.update.return_value.where.return_value = MagicMock()
            
            result = job_service.update_job_status(
                job_id="job123",
                status="processing",
                progress=0.5,
                current_stage="stage1"
            )
            
            assert result is True
    
    def test_update_job_completion(self):
        """Test marking job as completed."""
        from services import job_service
        
        with patch.object(job_service, 'Job') as mock_job_cls:
            mock_job = MagicMock(
                id="job123",
                status="processing",
                current_stage="processing"
            )
            mock_job_cls.get_by_id.return_value = mock_job
            
            result = job_service.update_job_completion(
                job_id="job123",
                report={"status": "success"}
            )
            
            assert result is True
            assert mock_job.status == "completed"
            mock_job.save.assert_called_once()
    
    def test_delete_job_success(self):
        """Test deleting a job."""
        from services import job_service
        
        with patch.object(job_service, 'JobRepository') as mock_repo, \
             patch.object(job_service, 'Path') as mock_path_cls:
            
            mock_job = MagicMock(id="job123", pdf_path="/path/file.pdf")
            mock_repo.get.return_value = mock_job
            mock_repo.delete.return_value = True
            
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path
            
            result = job_service.delete_job("job123")
            
            assert result is True
            mock_repo.delete.assert_called_once_with("job123")
    
    def test_store_artifacts(self):
        """Test storing artifacts for a job."""
        from services import job_service
        
        with patch.object(job_service, 'ArtifactRepository') as mock_repo:
            artifacts = [
                {"url": "https://github.com/repo", "type": "github_repo", "description": "Code"},
                {"url": "https://data.org", "type": "dataset", "description": "Dataset"}
            ]
            
            result = job_service.store_artifacts("job123", artifacts)
            
            assert result is True
            assert mock_repo.create.call_count == 2
    
    def test_get_job_artifacts(self):
        """Test retrieving artifacts for a job."""
        from services import job_service
        
        with patch.object(job_service, 'ArtifactRepository') as mock_repo:
            mock_artifacts = [
                MagicMock(url="https://github.com/repo", artifact_type="github_repo", description="Code"),
                MagicMock(url="https://data.org", artifact_type="dataset", description="Data")
            ]
            mock_repo.list_by_job.return_value = mock_artifacts
            
            result = job_service.get_job_artifacts("job123")
            
            assert len(result) == 2
            assert result[0]["url"] == "https://github.com/repo"


# ============================================================================
# AUTH SERVICE TESTS
# ============================================================================
class TestAuthService:
    """Test AuthService - password hashing and user validation."""
    
    def test_hash_password_returns_hashed_value(self):
        """Test that password hashing produces different output."""
        from services import auth_service
        
        password = "mypassword123"
        hashed = auth_service.hash_password(password)
        
        # Should not be the same as original
        assert hashed != password
        # Should be long (includes salt)
        assert len(hashed) > 50
        # Should contain the separator
        assert "$" in hashed
    
    def test_hash_password_produces_different_hashes(self):
        """Test that hashing same password twice produces different hashes."""
        from services import auth_service
        
        password = "mypassword123"
        hash1 = auth_service.hash_password(password)
        hash2 = auth_service.hash_password(password)
        
        # Different salts should produce different hashes
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        from services import auth_service
        
        password = "mypassword123"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        from services import auth_service
        
        password = "mypassword123"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password("wrongpassword", hashed) is False
    
    def test_get_user_by_username(self):
        """Test retrieving user by username."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_user = MagicMock(id=1, username="alice", email="alice@example.com")
            mock_repo.get_by_username.return_value = mock_user
            
            result = auth_service.get_user_by_username("alice")
            
            assert result.username == "alice"
            mock_repo.get_by_username.assert_called_once_with("alice")
    
    def test_get_user_by_id(self):
        """Test retrieving user by ID."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_user = MagicMock(id=1, username="alice")
            mock_repo.get_by_id.return_value = mock_user
            
            result = auth_service.get_user_by_id(1)
            
            assert result.id == 1
            mock_repo.get_by_id.assert_called_once_with(1)
    
    def test_user_exists_true(self):
        """Test checking if user exists (positive case)."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_repo.exists.return_value = True
            
            result = auth_service.user_exists("alice", "alice@example.com")
            
            assert result is True
    
    def test_user_exists_false(self):
        """Test checking if user exists (negative case)."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_repo.exists.return_value = False
            
            result = auth_service.user_exists("bob", "bob@example.com")
            
            assert result is False
    
    def test_create_user(self):
        """Test creating a new user."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_repo.create.return_value = 1
            
            result = auth_service.create_user("alice", "alice@example.com", "password123")
            
            assert result == 1
            mock_repo.create.assert_called_once()
    
    def test_update_password(self):
        """Test updating user password."""
        from services import auth_service
        
        with patch.object(auth_service, 'UserRepository') as mock_repo:
            mock_repo.update_password.return_value = True
            
            result = auth_service.update_password(1, "newpassword123")
            
            assert result is True
            mock_repo.update_password.assert_called_once()


# ============================================================================
# EVENT DISPATCHER TESTS
# ============================================================================
class TestEventDispatcher:
    """Test EventDispatcher - event emission and persistence."""
    
    def test_emit_event_persists_to_database(self):
        """Test that emit_event persists events to database."""
        from services.event_dispatcher import EventDispatcher
        from models.events import JobEvent
        
        mock_job_service = Mock()
        dispatcher = EventDispatcher(job_service=mock_job_service)
        
        event = JobEvent(
            job_id="job123",
            step="test_step",
            message="Test message",
            severity="info",
            progress=0.5
        )
        
        with patch.object(dispatcher, '_persist_event') as mock_persist:
            dispatcher.emit(event)
            mock_persist.assert_called_once_with(event)
    
    def test_emit_event_handles_stage_transitions(self):
        """Test that emit_event handles stage transitions."""
        from services.event_dispatcher import EventDispatcher
        from models.events import JobEvent
        
        dispatcher = EventDispatcher()
        
        event = JobEvent(
            job_id="job123",
            step="pdf_analysis_complete",
            message="PDF analysis complete",
            progress=0.33
        )
        
        with patch.object(dispatcher, '_handle_stage_transition') as mock_handler:
            dispatcher.emit(event)
            mock_handler.assert_called_once_with(event)
    
    def test_emit_event_logs_progress(self):
        """Test that emit_event logs progress values."""
        from services.event_dispatcher import EventDispatcher
        from models.events import JobEvent
        
        mock_logger = Mock()
        dispatcher = EventDispatcher(logger=mock_logger)
        
        event = JobEvent(
            job_id="job123",
            step="test_step",
            message="Test",
            progress=0.75
        )
        
        with patch.object(dispatcher, '_persist_event'):
            with patch.object(dispatcher, '_handle_stage_transition'):
                dispatcher.emit(event)
        
        # Verify logger was called with progress info
        assert any("progress" in str(call) for call in mock_logger.call_args_list)
    
    def test_event_dispatcher_factory_creates_test_dispatcher(self):
        """Test EventDispatcher factory creates test instances."""
        from services.event_dispatcher import EventDispatcher, EventDispatcherFactory
        
        dispatcher = EventDispatcherFactory.create_test_dispatcher()
        
        assert isinstance(dispatcher, EventDispatcher)
        assert dispatcher.event_queues == {}


# ============================================================================
# CACHE SERVICE TESTS
# ============================================================================
class TestCacheService:
    """Test CacheService - caching logic."""
    
    def test_get_cached_paper_analysis_hit(self):
        """Test cache hit for paper analysis."""
        from services import cache_service
        
        with patch('services.cache_service.Config') as mock_config, \
             patch.object(cache_service, 'CachePaperAnalysisRepository') as mock_repo:
            
            mock_config.ENABLE_CACHING = True
            mock_cache = MagicMock(
                title="Test Paper",
                abstract="Abstract",
                citations="[]",
                extracted_text="text",
                claimed_results="{}",
                methodology="Method",
                dependencies="deps",
                dataset_description="Dataset"
            )
            mock_repo.get_by_hash.return_value = mock_cache
            
            result = cache_service.get_cached_paper_analysis("hash123")
            
            assert result is not None
            assert result["title"] == "Test Paper"
    
    def test_get_cached_paper_analysis_miss(self):
        """Test cache miss for paper analysis."""
        from services import cache_service
        
        with patch('services.cache_service.Config') as mock_config, \
             patch.object(cache_service, 'CachePaperAnalysisRepository') as mock_repo:
            
            mock_config.ENABLE_CACHING = True
            mock_repo.get_by_hash.return_value = None
            
            result = cache_service.get_cached_paper_analysis("hash123")
            
            assert result is None
    
    def test_get_cached_paper_analysis_disabled(self):
        """Test cache disabled for paper analysis."""
        from services import cache_service
        
        with patch('services.cache_service.Config') as mock_config:
            mock_config.ENABLE_CACHING = False
            
            result = cache_service.get_cached_paper_analysis("hash123")
            
            assert result is None
    
    def test_store_paper_analysis_cache(self):
        """Test storing paper analysis in cache."""
        from services import cache_service
        
        with patch('services.cache_service.Config') as mock_config, \
             patch.object(cache_service, 'CachePaperAnalysis') as mock_model:
            
            mock_config.ENABLE_CACHING = True
            mock_model.get.side_effect = Exception("DoesNotExist")
            mock_model.create.return_value = MagicMock()
            
            paper_info = {
                "title": "Paper",
                "abstract": "Abstract",
                "citations": [],
                "claimed_results": {},
                "methodology": "Method",
                "dependencies": "deps",
                "dataset_description": "Dataset"
            }
            
            cache_service.store_paper_analysis_cache("hash123", "text", paper_info)
            
            mock_model.create.assert_called_once()
    
    def test_get_cached_evaluation_hit(self):
        """Test cache hit for evaluation."""
        from services import cache_service
        
        with patch('services.cache_service.Config') as mock_config, \
             patch.object(cache_service, 'CacheEvaluationRepository') as mock_repo:
            
            mock_config.ENABLE_CACHING = True
            eval_data = {"aspects": [{"name": "test", "status": "pass"}]}
            mock_cache = MagicMock(evaluations=json.dumps(eval_data))
            mock_repo.get.return_value = mock_cache
            
            result = cache_service.get_cached_evaluation("paper_hash", "code_hash")
            
            assert result is not None
            assert result["aspects"][0]["name"] == "test"
    
    def test_get_cache_stats(self):
        """Test retrieving cache statistics."""
        from services import cache_service
        
        with patch.object(cache_service, 'ExecutionDetails') as mock_exec, \
             patch.object(cache_service, 'PaperAnalysis') as mock_paper, \
             patch.object(cache_service, 'AspectEvaluation') as mock_eval:
            
            mock_exec.select.return_value.where.return_value.count.return_value = 5
            mock_paper.select.return_value.where.return_value.count.return_value = 3
            mock_eval.select.return_value.distinct.return_value.count.return_value = 2
            
            result = cache_service.get_cache_stats()
            
            assert result["paper_analysis"] == 3
            assert result["code_execution"] == 5
            assert result["evaluation"] == 2


# ============================================================================
# ANALYSIS SERVICE TESTS
# ============================================================================
class TestAnalysisService:
    """Test AnalysisService - paper analysis."""
    
    def test_extract_and_analyze_pdf_success(self):
        """Test successful PDF extraction and analysis."""
        from services import analysis_service
        
        with patch.object(analysis_service, 'extract_pdf_text') as mock_extract, \
             patch.object(analysis_service, 'parse_paper_with_claude') as mock_parse, \
             patch.object(analysis_service, 'store_paper_analysis') as mock_store, \
             patch('services.analysis_service.Config') as mock_config:
            
            mock_config.ENABLE_CACHING = False
            mock_extract.return_value = "PDF text content"
            mock_parse.return_value = {
                "title": "Test Paper",
                "abstract": "Abstract",
                "citations": [],
                "artifacts": []
            }
            
            mock_llm = Mock()
            result = analysis_service.extract_and_analyze_pdf(
                pdf_path="/path/file.pdf",
                job_id="job123",
                llm_provider=mock_llm
            )
            
            assert result[0] == "PDF text content"
            assert result[1]["title"] == "Test Paper"
    
    def test_parse_paper_with_claude(self):
        """Test parsing paper with Claude."""
        from services import analysis_service
        
        mock_llm = Mock()
        mock_llm.get_name.return_value = "anthropic"
        mock_llm.get_model.return_value = "claude-3"
        response_json = json.dumps({
            "title": "Test Paper",
            "abstract": "Abstract text",
            "citations": [],
            "artifacts": []
        })
        mock_llm.complete.return_value = response_json
        
        result = analysis_service.parse_paper_with_claude(
            pdf_text="Some PDF content",
            llm_provider=mock_llm
        )
        
        assert result["title"] == "Test Paper"
        mock_llm.complete.assert_called_once()
    
    def test_parse_paper_with_claude_markdown_json(self):
        """Test parsing paper when Claude returns markdown-wrapped JSON."""
        from services import analysis_service
        
        mock_llm = Mock()
        mock_llm.get_name.return_value = "anthropic"
        mock_llm.get_model.return_value = "claude-3"
        
        response_json = json.dumps({
            "title": "Test Paper",
            "abstract": "Abstract",
            "citations": [],
            "artifacts": []
        })
        mock_llm.complete.return_value = f"```json\n{response_json}\n```"
        
        result = analysis_service.parse_paper_with_claude(
            pdf_text="Some PDF content",
            llm_provider=mock_llm
        )
        
        assert result["title"] == "Test Paper"
    
    def test_store_paper_analysis(self):
        """Test storing paper analysis."""
        from services import analysis_service
        
        with patch.object(analysis_service, 'PaperAnalysis') as mock_model:
            paper_info = {
                "title": "Paper",
                "abstract": "Abstract",
                "citations": [],
                "claimed_results": {},
                "methodology": "Method",
                "dependencies": "deps",
                "dataset_description": "Dataset"
            }
            
            analysis_service.store_paper_analysis(
                job_id="job123",
                paper_info=paper_info,
                pdf_text="text content"
            )
            
            mock_model.create.assert_called_once()


# ============================================================================
# EVALUATION SERVICE TESTS
# ============================================================================
class TestEvaluationService:
    """Test EvaluationService - reproducibility evaluation."""
    
    def test_evaluate_reproducibility_aspects_success(self):
        """Test successful aspect evaluation."""
        from services import evaluation_service
        
        with patch.object(evaluation_service, 'PaperAnalysisRepository') as mock_paper_repo, \
             patch.object(evaluation_service, 'ExecutionDetailsRepository') as mock_exec_repo, \
             patch.object(evaluation_service, 'AspectEvaluation') as mock_eval, \
             patch.object(evaluation_service, 'Job') as mock_job, \
             patch('services.evaluation_service.Config') as mock_config:
            
            mock_config.ENABLE_CACHING = False
            
            # Mock paper analysis
            mock_paper = MagicMock(
                pdf_hash="hash1",
                title="Paper",
                abstract="Abstract",
                extracted_text="text",
                methodology="Method",
                dependencies="deps",
                dataset_description="Dataset",
                claimed_results="{}"
            )
            mock_paper.get_claimed_results.return_value = {}
            mock_paper_repo.get.return_value = mock_paper
            
            # Mock execution details
            mock_exec = MagicMock(
                stdout_combined="output",
                commands_run="commands",
                dependencies_used="deps",
                errors_summary="errors",
                test_info="test",
                randomness_info="seed",
                discovered_files="[]",
                actual_results="{}"
            )
            mock_exec.get_discovered_files.return_value = []
            mock_exec.get_actual_results.return_value = {}
            mock_exec_repo.get.return_value = mock_exec
            
            # Mock job
            mock_job_inst = MagicMock()
            mock_job.get_by_id.return_value = mock_job_inst
            
            mock_llm = Mock()
            mock_llm.get_name.return_value = "anthropic"
            eval_response = json.dumps({
                "evaluations": [
                    {
                        "aspect_id": "test",
                        "name": "Test Aspect",
                        "status": "pass",
                        "evidence": "Evidence",
                        "paper_supports": True,
                        "code_supports": True,
                        "conclusion": "Pass"
                    }
                ]
            })
            mock_llm.complete.return_value = eval_response
            
            result = evaluation_service.evaluate_reproducibility_aspects(
                job_id="job123",
                llm_provider=mock_llm
            )
            
            assert result is True
            mock_eval.create.assert_called()


# ============================================================================
# LLM SERVICE TESTS
# ============================================================================
class TestLLMService:
    """Test LLMService - LLM provider initialization."""
    
    def test_init_llm_provider_success(self):
        """Test successful LLM provider initialization."""
        from services import llm_service
        
        with patch.object(llm_service, 'get_provider') as mock_get:
            mock_provider = Mock()
            mock_provider.get_name.return_value = "anthropic"
            mock_provider.get_model.return_value = "claude-3"
            mock_get.return_value = mock_provider
            
            result = llm_service.init_llm_provider()
            
            assert result == mock_provider
    
    def test_init_llm_provider_failure(self):
        """Test LLM provider initialization failure."""
        from services import llm_service
        
        with patch.object(llm_service, 'get_provider') as mock_get:
            mock_get.side_effect = Exception("API key missing")
            
            with pytest.raises(Exception):
                llm_service.init_llm_provider()


# ============================================================================
# ANTHROPIC PROVIDER TESTS
# ============================================================================
class TestAnthropicProvider:
    """Test AnthropicProvider - Anthropic Claude provider."""
    
    def test_anthropic_provider_initialization(self):
        """Test Anthropic provider initialization."""
        from llm.anthropic_provider import AnthropicProvider
        
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test-key', 'ANTHROPIC_MODEL': 'claude-3'}):
            with patch('llm.anthropic_provider.Anthropic') as mock_anthropic_cls:
                provider = AnthropicProvider()
                
                assert provider.model == 'claude-3'
                mock_anthropic_cls.assert_called_once()
    
    def test_anthropic_provider_initialization_no_key(self):
        """Test Anthropic provider initialization without API key."""
        from llm.anthropic_provider import AnthropicProvider
        
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError):
                AnthropicProvider()
    
    def test_anthropic_provider_complete(self):
        """Test Anthropic provider text completion."""
        from llm.anthropic_provider import AnthropicProvider
        
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test-key'}):
            with patch('llm.anthropic_provider.Anthropic') as mock_anthropic_cls:
                mock_client = Mock()
                mock_anthropic_cls.return_value = mock_client
                
                mock_response = Mock()
                mock_response.content = [Mock(text="Response text")]
                mock_client.messages.create.return_value = mock_response
                
                provider = AnthropicProvider(model="test-model")
                result = provider.complete(messages=[{"role": "user", "content": "test"}])
                
                assert result == "Response text"
    
    def test_anthropic_provider_get_name(self):
        """Test Anthropic provider name."""
        from llm.anthropic_provider import AnthropicProvider
        
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test-key'}):
            with patch('llm.anthropic_provider.Anthropic'):
                provider = AnthropicProvider()
                assert provider.get_name() == "anthropic"


# ============================================================================
# OLLAMA PROVIDER TESTS
# ============================================================================
class TestOllamaProvider:
    """Test OllamaProvider - Ollama local LLM provider."""
    
    def test_ollama_provider_initialization_success(self):
        """Test Ollama provider initialization with connection."""
        from llm.ollama_provider import OllamaProvider
        
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://localhost:11434'}):
            with patch('llm.ollama_provider.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                
                provider = OllamaProvider(model="llama2")
                
                assert provider.model == "llama2"
                assert provider.base_url == "http://localhost:11434"
    
    def test_ollama_provider_initialization_no_connection(self):
        """Test Ollama provider initialization without connection."""
        from llm.ollama_provider import OllamaProvider
        
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://localhost:11434'}):
            with patch('llm.ollama_provider.requests.get') as mock_get:
                mock_get.side_effect = Exception("Connection refused")
                
                with pytest.raises(ValueError):
                    OllamaProvider(model="llama2")
    
    def test_ollama_provider_complete(self):
        """Test Ollama provider text completion."""
        from llm.ollama_provider import OllamaProvider
        
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://localhost:11434'}):
            with patch('llm.ollama_provider.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                
                with patch('llm.ollama_provider.requests.post') as mock_post:
                    mock_post_response = Mock()
                    mock_post_response.json.return_value = {
                        "message": {"content": "Response text"}
                    }
                    mock_post.return_value = mock_post_response
                    
                    provider = OllamaProvider(model="llama2")
                    result = provider.complete(messages=[{"role": "user", "content": "test"}])
                    
                    assert result == "Response text"
    
    def test_ollama_provider_get_name(self):
        """Test Ollama provider name."""
        from llm.ollama_provider import OllamaProvider
        
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://localhost:11434'}):
            with patch('llm.ollama_provider.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                
                provider = OllamaProvider()
                assert provider.get_name() == "ollama"


# ============================================================================
# DOCKER SERVICE TESTS
# ============================================================================
class TestDockerService:
    """Test DockerService - Docker container operations."""
    
    def test_docker_service_init_success(self):
        """Test Docker service initialization."""
        from services import docker_service
        
        with patch('services.docker_service.docker.from_env') as mock_docker:
            docker_service.init_docker()
            
            assert docker_service.DOCKER_AVAILABLE is True
            mock_docker.assert_called_once()
    
    def test_docker_service_init_failure(self):
        """Test Docker service initialization failure."""
        from services import docker_service
        
        with patch('services.docker_service.docker.from_env') as mock_docker:
            mock_docker.side_effect = Exception("Docker not available")
            
            result = docker_service.init_docker()
            
            assert result is False
            assert docker_service.DOCKER_AVAILABLE is False
    
    def test_is_docker_available(self):
        """Test checking if Docker is available."""
        from services import docker_service
        
        docker_service.DOCKER_AVAILABLE = True
        assert docker_service.is_docker_available() is True
        
        docker_service.DOCKER_AVAILABLE = False
        assert docker_service.is_docker_available() is False
    
    def test_validate_network_exists(self):
        """Test validating Docker network that exists."""
        from services import docker_service
        
        docker_service.DOCKER_AVAILABLE = True
        
        with patch.object(docker_service, 'DOCKER_CLIENT') as mock_client:
            mock_network = Mock(name="test-network")
            mock_client.networks.list.return_value = [mock_network]
            
            exists, error = docker_service.validate_network("test-network")
            
            assert exists is True
            assert error is None
    
    def test_validate_network_not_exists(self):
        """Test validating Docker network that doesn't exist."""
        from services import docker_service
        
        docker_service.DOCKER_AVAILABLE = True
        
        with patch.object(docker_service, 'DOCKER_CLIENT') as mock_client:
            mock_client.networks.list.return_value = []
            
            exists, error = docker_service.validate_network("missing-network")
            
            assert exists is False
            assert error is not None
            assert "missing-network" in error
    
    def test_build_agent_image_success(self):
        """Test building Docker agent image."""
        from services import docker_service
        
        docker_service.DOCKER_AVAILABLE = True
        
        with patch.object(docker_service, 'DOCKER_CLIENT') as mock_client:
            result = docker_service.build_agent_image()
            
            assert result is True
            mock_client.images.build.assert_called_once()
    
    def test_build_agent_image_failure(self):
        """Test Docker agent image build failure."""
        from services import docker_service
        
        docker_service.DOCKER_AVAILABLE = True
        
        with patch.object(docker_service, 'DOCKER_CLIENT') as mock_client:
            mock_client.images.build.side_effect = Exception("Build failed")
            
            result = docker_service.build_agent_image()
            
            assert result is False


# ============================================================================
# PIPELINE ORCHESTRATOR TESTS
# ============================================================================
class TestPipelineOrchestrator:
    """Test PipelineOrchestrator - stage orchestration."""
    
    def test_orchestrator_initialization(self):
        """Test PipelineOrchestrator initialization."""
        from services.pipeline_orchestrator import PipelineOrchestrator
        from services.event_dispatcher import EventDispatcher
        
        dispatcher = EventDispatcher()
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)
        
        assert orchestrator.dispatcher == dispatcher
    
    def test_orchestrator_emit_event(self):
        """Test PipelineOrchestrator emitting events."""
        from services.pipeline_orchestrator import PipelineOrchestrator
        
        mock_dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=mock_dispatcher)
        
        orchestrator.emit_event(
            job_id="job123",
            step="test_step",
            message="Test message",
            progress=0.5
        )
        
        mock_dispatcher.emit.assert_called_once()
    
    def test_orchestrator_default_logger(self):
        """Test PipelineOrchestrator default logger."""
        from services.pipeline_orchestrator import PipelineOrchestrator
        
        orchestrator = PipelineOrchestrator()
        
        # Should not raise an error
        orchestrator.logger("Test message")


# ============================================================================
# PROVIDER FACTORY TESTS
# ============================================================================
class TestProviderFactory:
    """Test LLM provider factory."""
    
    def test_get_provider_returns_provider(self):
        """Test that get_provider returns an LLM provider."""
        from llm import get_provider
        
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test-key'}):
            with patch('llm.anthropic_provider.Anthropic'):
                provider = get_provider()
                
                assert provider is not None
                assert hasattr(provider, 'complete')
                assert hasattr(provider, 'get_name')
                assert hasattr(provider, 'get_model')
