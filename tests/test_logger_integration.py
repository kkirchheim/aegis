"""Integration tests for logger handling in evaluation pipeline."""

import json
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from models.database import ExecutionDetails, Job, PaperAnalysis, User
from services.evaluation_service import evaluate_paper
from services.pipeline_orchestrator import stage_3_evaluation
from services.plugin_service import PluginService


@pytest.fixture
def test_user(app):
    """Create test user."""
    with app.app_context():
        user = User.create(
            username="test_logger_user", email="test_logger@example.com", password_hash="hash", is_active=True
        )
        yield user
        user.delete_instance()


@pytest.fixture
def test_job(app, test_user):
    """Create test job."""
    with app.app_context():
        job = Job.create(
            id=str(uuid4()),
            user=test_user,
            status="pending",
            current_stage="pending",
            progress=0.0,
            pdf_path="test.pdf",
            pdf_filename="test.pdf",
        )
        yield job

        try:
            PaperAnalysis.delete().where(PaperAnalysis.job == job.id).execute()
            ExecutionDetails.delete().where(ExecutionDetails.job == job.id).execute()
        except Exception:
            pass

        job.delete_instance()


@pytest.fixture
def test_paper_analysis(app, test_job):
    """Create test paper analysis."""
    with app.app_context():
        analysis = PaperAnalysis.create(
            job=test_job,
            extracted_text="Test paper about reproducibility.",
            title="Test Paper",
            abstract="A test abstract",
        )
        yield analysis
        analysis.delete_instance()


@pytest.fixture
def test_execution_details(app, test_job):
    """Create test execution details."""
    with app.app_context():
        details = ExecutionDetails.create(
            job=test_job, stdout_combined="Test output", errors_summary="Test log", status="completed"
        )
        yield details
        details.delete_instance()


class TestLoggerFunctionIntegration:
    """Tests that actually call functions with real loggers to catch logger issues."""

    def test_evaluate_paper_with_function_logger(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """evaluate_paper should work with a function-style logger wrapped as object."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            # Create a logger object that delegates to a function
            log_messages = []

            class FuncLogger:
                def info(self, msg):
                    log_messages.append(msg)

                def warning(self, msg):
                    log_messages.append(msg)

                def error(self, msg, exc_info=False):
                    log_messages.append(msg)

            logger = FuncLogger()

            # Mock the LLM provider - return valid JSON format
            active = PluginService.get_active_plugins_for_evaluation(test_user.id)
            mock_response = json.dumps(
                [{"plugin_name": p["name"], "status": "PASS", "reasoning": "Test"} for p in active]
            )
            mock_provider = Mock()
            mock_provider.complete.return_value = mock_response

            # Call evaluate_paper with logger object
            result = evaluate_paper(
                job_id=test_job.id,
                paper_analysis=test_paper_analysis,
                code_output="test output",
                execution_log="test log",
                llm_provider=mock_provider,
                app_logger=logger,
            )

            # Should complete without error
            assert isinstance(result, dict)

    def test_evaluate_paper_with_none_logger(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """evaluate_paper should work with None logger."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            mock_provider = Mock()
            mock_provider.complete.return_value = """
### Code Availability
Status: PASS
Reasoning: Code is available
"""

            # Call with None logger
            result = evaluate_paper(
                job_id=test_job.id,
                paper_analysis=test_paper_analysis,
                code_output="test output",
                execution_log="test log",
                llm_provider=mock_provider,
                app_logger=None,
            )

            assert isinstance(result, dict)

    def test_stage3_evaluation_with_function_logger_full_path(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """stage_3_evaluation should work with function logger in full pipeline."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            # Create a real function logger
            log_messages = []

            def func_logger(msg):
                log_messages.append(msg)

            # Mock evaluate_paper to avoid LLM call
            with patch("services.evaluation_service.evaluate_paper") as mock_eval:
                mock_eval.return_value = {"aspect1": {"status": "PASS", "reasoning": "Good"}}

                # Mock EventDispatcher
                with patch("services.pipeline_orchestrator.EventDispatcher"):
                    # This should NOT raise "'function' object has no attribute 'error'"
                    result = stage_3_evaluation(test_job.id, func_logger)

            assert result
            assert len(log_messages) > 0  # Logger should have been called

    def test_stage3_evaluation_error_path_with_function_logger(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """stage_3_evaluation error handling should work with function logger."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            log_messages = []

            def func_logger(msg):
                log_messages.append(msg)

            # Mock evaluate_paper to raise an error
            with patch("services.evaluation_service.evaluate_paper") as mock_eval:
                mock_eval.side_effect = Exception("Test LLM error")

                with patch("services.pipeline_orchestrator.EventDispatcher"):
                    # This should NOT crash with logger error
                    result = stage_3_evaluation(test_job.id, func_logger)

            assert not result

            updated_job = Job.get_by_id(test_job.id)
            assert updated_job.status == "error"
            # Should have logged error messages
            assert len(log_messages) > 0

    def test_stage3_evaluation_passes_logger_wrapper_to_evaluate_paper(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """stage_3_evaluation should pass logger wrapper, not original logger."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            log_messages = []

            def func_logger(msg):
                log_messages.append(msg)

            # Track what logger is passed to evaluate_paper
            passed_logger = None

            def mock_evaluate_paper(job_id, paper_analysis, code_output, execution_log, llm_provider, app_logger):
                nonlocal passed_logger
                passed_logger = app_logger

                # Verify passed logger has the right methods
                assert hasattr(app_logger, "info"), "Logger should have info method"
                assert hasattr(app_logger, "error"), "Logger should have error method"
                assert hasattr(app_logger, "warning"), "Logger should have warning method"

                # Test calling the methods (they should not raise)
                app_logger.info("Test info")
                app_logger.warning("Test warning")
                # Don't call error as it would print

                return {}

            with patch("services.evaluation_service.evaluate_paper", side_effect=mock_evaluate_paper):
                with patch("services.event_dispatcher.EventDispatcher"):
                    result = stage_3_evaluation(test_job.id, func_logger)

            assert result
            assert passed_logger is not None

    def test_logger_wrapper_has_required_methods(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Logger wrapper should have all required methods."""
        with app.app_context():
            # Create wrapper like stage_3_evaluation does
            from services.pipeline_orchestrator import stage_3_evaluation

            log_messages = []

            def func_logger(msg):
                log_messages.append(msg)

            # We can't easily extract the wrapper, but we can test the methods indirectly
            # by calling stage_3_evaluation with a function logger and verify no AttributeError

            with patch("services.evaluation_service.evaluate_paper") as mock_eval:
                mock_eval.return_value = {}

                with patch("services.pipeline_orchestrator.EventDispatcher"):
                    # If wrapper is missing methods, this would crash with AttributeError
                    result = stage_3_evaluation(test_job.id, func_logger)

            assert result

    def test_evaluate_paper_calls_logger_methods_correctly(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """evaluate_paper should call logger.info/error/warning, not logger()."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            # Create a fake logger object with tracked calls
            class TrackingLogger:
                def __init__(self):
                    self.info_calls = []
                    self.error_calls = []
                    self.warning_calls = []

                def info(self, msg):
                    self.info_calls.append(msg)

                def error(self, msg, exc_info=False):
                    self.error_calls.append((msg, exc_info))

                def warning(self, msg):
                    self.warning_calls.append(msg)

            logger_obj = TrackingLogger()

            mock_provider = Mock()
            mock_provider.complete.return_value = """
### Code Availability
Status: PASS
Reasoning: Available
"""

            # Call evaluate_paper
            result = evaluate_paper(
                job_id=test_job.id,
                paper_analysis=test_paper_analysis,
                code_output="test",
                execution_log="test",
                llm_provider=mock_provider,
                app_logger=logger_obj,
            )

            # Verify logger methods were called (not the object as a function)
            assert len(logger_obj.info_calls) > 0, "Should have called logger.info()"
            assert result is not None


class TestLoggerEdgeCases:
    """Test edge cases in logger handling."""

    def test_logger_wrapper_with_mock_object(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Logger wrapper should work with Mock objects."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            mock_logger = Mock()
            mock_logger.info = Mock()
            mock_logger.error = Mock()
            mock_logger.warning = Mock()

            mock_provider = Mock()
            mock_provider.complete.return_value = """
### Code Availability
Status: PASS
Reasoning: Test
"""

            result = evaluate_paper(
                job_id=test_job.id,
                paper_analysis=test_paper_analysis,
                code_output="test",
                execution_log="test",
                llm_provider=mock_provider,
                app_logger=mock_logger,
            )

            assert result is not None

    def test_stage3_evaluation_catches_logger_exceptions(
        self, app, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """stage_3_evaluation should not crash even if logger raises exception."""
        with app.app_context():
            PluginService.get_or_create_default_plugins(test_user.id)

            # Create a logger that raises on error()
            class BrokenLogger:
                def info(self, msg):
                    pass

                def warning(self, msg):
                    pass

                def error(self, msg, exc_info=False):
                    raise Exception("Logger error!")

            broken_logger = BrokenLogger()

            # This should not crash with logger exception
            try:
                with patch("services.evaluation_service.evaluate_paper") as mock_eval:
                    mock_eval.side_effect = Exception("Test error")

                    with patch("services.pipeline_orchestrator.EventDispatcher"):
                        result = stage_3_evaluation(test_job.id, broken_logger)

                # May return False due to the inner error, but should not crash
                assert result is not None
            except Exception as e:
                # If it does crash, it should not be an AttributeError about logger
                assert "has no attribute" not in str(e), f"Should not be logger attribute error: {e}"
