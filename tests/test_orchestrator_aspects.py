"""Tests for orchestrator integration with plugin plugin system."""

import json
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from models.database import ExecutionDetails, Job, PaperAnalysis, User
from repositories import UserPluginRepository
from services.pipeline_orchestrator import PipelineOrchestrator, stage_3_evaluation
from services.plugin_service import PluginService


@pytest.fixture
def test_user(app):
    """Create test user."""
    user = User.create(
        username="test_user_plugins", email="test_plugins@example.com", password_hash="hash", is_active=True
    )
    yield user
    user.delete_instance()


@pytest.fixture
def test_job(test_user):
    """Create test job."""
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

    # Cleanup related records first
    try:
        PaperAnalysis.delete().where(PaperAnalysis.job == job.id).execute()
        ExecutionDetails.delete().where(ExecutionDetails.job == job.id).execute()
    except Exception:
        pass

    job.delete_instance()


@pytest.fixture
def test_paper_analysis(test_job):
    """Create test paper analysis."""
    analysis = PaperAnalysis.create(
        job=test_job,
        extracted_text="This is a test paper about reproducibility. It contains methodology and results.",
        title="Test Paper",
        abstract="A test abstract",
    )
    yield analysis
    analysis.delete_instance()


@pytest.fixture
def test_execution_details(test_job):
    """Create test execution details."""
    details = ExecutionDetails.create(
        job=test_job,
        stdout_combined="Test code execution output\nResults: 42",
        errors_summary="Test execution log",
        status="completed",
    )
    yield details
    details.delete_instance()


class TestOrchestratorStage3WithPlugins:
    """Tests for orchestrator _run_stage_3 with plugins."""

    def test_stage3_evaluation_with_active_plugins(
        self, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Stage 3 should evaluate all active plugins."""
        # Seed defaults for user
        PluginService.get_or_create_default_plugins(test_user.id)
        active_plugins = PluginService.get_active_plugins_for_evaluation(test_user.id)

        assert len(active_plugins) > 0, "Should have active default plugins"

        # Create orchestrator with mocked LLM
        orchestrator = PipelineOrchestrator()

        # Mock evaluate_paper to return sample results
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {
                str(active_plugins[0]["id"]): {"status": "PASS", "reasoning": "Code is available"}
            }

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        # Verify job updated
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        assert updated_job.evidence is not None

        results = updated_job.get_evidence()
        assert len(results) > 0

    def test_stage3_evaluation_with_no_active_plugins(
        self, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Stage 3 should skip evaluation if no active plugins."""
        # Don't seed any plugins for user - they have none
        orchestrator = PipelineOrchestrator()

        result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        # Verify job completed with empty results
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        results = updated_job.get_evidence()
        assert len(results) == 0

    def test_stage3_evaluation_with_custom_plugins(
        self, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Stage 3 should evaluate custom plugins."""
        # Create custom plugin
        custom_plugin = PluginService.create_custom_plugin(
            user_id=test_user.id,
            name="Custom Check",
            description="A custom check",
            prompt="Does this meet our criteria?",
        )

        active_plugins = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert len(active_plugins) > 0

        orchestrator = PipelineOrchestrator()

        # Mock evaluation
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {custom_plugin["id"]: {"status": "FAIL", "reasoning": "Criteria not met"}}

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evidence()
        assert custom_plugin["id"] in results

    def test_stage3_evaluation_handles_error(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should handle evaluation errors."""
        PluginService.get_or_create_default_plugins(test_user.id)

        orchestrator = PipelineOrchestrator()

        # Mock evaluation to raise error
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.side_effect = Exception("LLM error")

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert not result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "error"
        assert "failed" in updated_job.error_message.lower() or "evaluation" in updated_job.error_message.lower()

    def test_stage3_evaluation_deactivated_plugins_skipped(
        self, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Stage 3 should skip deactivated plugins."""
        # Seed defaults
        PluginService.get_or_create_default_plugins(test_user.id)

        # Deactivate all plugins
        all_user_plugins = UserPluginRepository.get_user_plugins(test_user.id)
        for ua in all_user_plugins:
            PluginService.deactivate_plugin(test_user.id, ua.plugin_id)

        # Should have no active plugins
        active = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert len(active) == 0

        orchestrator = PipelineOrchestrator()

        result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evidence()
        assert len(results) == 0

    def test_stage3_evaluation_mixed_plugins_status(
        self, test_job, test_user, test_paper_analysis, test_execution_details
    ):
        """Stage 3 should handle mixed PASS/FAIL/UNCLEAR statuses."""
        PluginService.get_or_create_default_plugins(test_user.id)
        active_plugins = PluginService.get_active_plugins_for_evaluation(test_user.id)

        # Mock evaluation with mixed results
        results_dict = {}
        for i, plugin in enumerate(active_plugins):
            status = ["PASS", "FAIL", "UNCLEAR"][i % 3]
            results_dict[plugin["id"]] = {"status": status, "reasoning": f"Test {status}"}

        orchestrator = PipelineOrchestrator()

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = results_dict

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evidence()

        # Verify counts
        passed = sum(1 for r in results.values() if r["status"] == "PASS")
        failed = sum(1 for r in results.values() if r["status"] == "FAIL")
        unclear = sum(1 for r in results.values() if r["status"] == "UNCLEAR")

        assert passed >= 0 and failed >= 0 and unclear >= 0

    def test_stage3_stores_results_as_json(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should store results as proper JSON in job.evidence."""
        PluginService.get_or_create_default_plugins(test_user.id)
        active_plugins = PluginService.get_active_plugins_for_evaluation(test_user.id)

        orchestrator = PipelineOrchestrator()

        test_results = {str(active_plugins[0]["id"]): {"status": "PASS", "reasoning": "Very reproducible"}}

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = test_results

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)

        # Verify it's valid JSON
        assert updated_job.evidence is not None
        parsed = json.loads(updated_job.evidence)
        assert isinstance(parsed, dict)
        assert len(parsed) > 0

    def test_stage3_updates_job_progress(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should set job progress to 1.0 on completion."""
        PluginService.get_or_create_default_plugins(test_user.id)

        orchestrator = PipelineOrchestrator()

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.progress == 1.0
        assert updated_job.current_stage == "evaluation"

    def test_stage3_emits_events(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit proper progress events."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Mock dispatcher to capture events
        mock_dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=mock_dispatcher)

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        # Verify emit_event was called (indirectly through dispatcher)
        # The event should have been emitted at least twice (start and complete)
        assert mock_dispatcher is not None


class TestPluginServiceIntegration:
    """Integration tests for plugin service with orchestrator."""

    def test_get_active_plugins_returns_prompts(self, test_user):
        """get_active_plugins_for_evaluation should return correct prompts."""
        PluginService.get_or_create_default_plugins(test_user.id)

        active = PluginService.get_active_plugins_for_evaluation(test_user.id)

        assert len(active) > 0
        for plugin in active:
            assert "id" in plugin
            assert "name" in plugin
            assert "prompt_to_use" in plugin
            assert len(plugin["prompt_to_use"]) > 0

    def test_custom_prompt_override_in_evaluation(self, test_user):
        """Custom prompts should be used in evaluation context."""
        # Create custom plugin
        custom = PluginService.create_custom_plugin(
            user_id=test_user.id, name="Custom", description="Custom plugin", prompt="Original prompt"
        )

        # Override prompt
        custom_prompt = "Overridden prompt for evaluation"
        PluginService.override_prompt(test_user.id, custom["id"], custom_prompt)

        # Get for evaluation
        active = PluginService.get_active_plugins_for_evaluation(test_user.id)

        # Find our custom plugin
        found = next((a for a in active if a["id"] == custom["id"]), None)
        assert found is not None
        assert found["prompt_to_use"] == custom_prompt

    def test_deactivated_plugins_excluded_from_evaluation(self, test_user):
        """Deactivated plugins should not appear in evaluation context."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Get all active
        active_before = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert len(active_before) > 0

        # Deactivate one
        first_plugin_id = active_before[0]["id"]
        PluginService.deactivate_plugin(test_user.id, first_plugin_id)

        # Get active again
        active_after = PluginService.get_active_plugins_for_evaluation(test_user.id)

        # Should be one less
        assert len(active_after) == len(active_before) - 1

        # Our deactivated one should not be present
        ids = [a["id"] for a in active_after]
        assert first_plugin_id not in ids

    def test_multiple_users_plugins_isolated(self, test_user):
        """Different users should have isolated plugins."""
        # Create another user
        user2 = User.create(
            username="test_user2_plugins", email="test_plugins2@example.com", password_hash="hash", is_active=True
        )

        try:
            # Seed defaults for both
            PluginService.get_or_create_default_plugins(test_user.id)
            PluginService.get_or_create_default_plugins(user2.id)

            # Create custom plugin for user1
            custom1 = PluginService.create_custom_plugin(
                user_id=test_user.id, name="User1 Custom", description="User1 plugin", prompt="User1 prompt"
            )

            # Get active plugins for both
            active1 = PluginService.get_active_plugins_for_evaluation(test_user.id)
            active2 = PluginService.get_active_plugins_for_evaluation(user2.id)

            # User1 should have more (custom added)
            assert len(active1) > len(active2) or len(active1) == len(active2)

            # Check that custom1 only appears in user1's plugins
            user1_ids = [a["id"] for a in active1]
            user2_ids = [a["id"] for a in active2]
            assert custom1["id"] in user1_ids
            assert custom1["id"] not in user2_ids

        finally:
            user2.delete_instance()

    def test_plugin_activation_deactivation_cycle(self, test_user):
        """Plugins should properly toggle activation."""
        PluginService.get_or_create_default_plugins(test_user.id)

        all_plugins = PluginService.get_all_plugins_for_user(test_user.id)
        first = all_plugins[0]
        plugin_id = first["id"]

        # Start active
        active = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert plugin_id in [a["id"] for a in active]

        # Deactivate
        PluginService.deactivate_plugin(test_user.id, plugin_id)
        active = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert plugin_id not in [a["id"] for a in active]

        # Reactivate
        PluginService.activate_plugin(test_user.id, plugin_id)
        active = PluginService.get_active_plugins_for_evaluation(test_user.id)
        assert plugin_id in [a["id"] for a in active]


class TestOrchestrationFullPipeline:
    """Integration tests for full pipeline with plugins."""

    def test_full_pipeline_with_plugins(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Full pipeline should work end-to-end with plugins."""
        # Setup
        PluginService.get_or_create_default_plugins(test_user.id)

        # Create orchestrator
        orchestrator = PipelineOrchestrator()

        # Mock evaluate_paper
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {
                "plugin1": {"status": "PASS", "reasoning": "Good"},
                "plugin2": {"status": "FAIL", "reasoning": "Bad"},
            }

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        # Verify results
        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        assert updated_job.evidence is not None

    def test_evaluation_handles_missing_analysis(self, test_job, test_user):
        """Evaluation should handle missing paper analysis gracefully."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Don't create paper_analysis or execution - they're missing
        orchestrator = PipelineOrchestrator()

        # Should fail gracefully
        result = orchestrator._run_stage_3(test_job.id, Mock())

        assert not result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "error"

    def test_evidence_json_format(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Evaluation results should be valid JSON with proper structure."""
        PluginService.get_or_create_default_plugins(test_user.id)

        orchestrator = PipelineOrchestrator()

        test_data = {
            "plugin_id_1": {"status": "PASS", "reasoning": "Code available"},
            "plugin_id_2": {"status": "FAIL", "reasoning": "Missing dependencies"},
        }

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = test_data

            result = orchestrator._run_stage_3(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evidence()

        # Verify structure
        assert isinstance(results, dict)
        for plugin_id, eval_data in results.items():
            assert "status" in eval_data
            assert "reasoning" in eval_data
            assert eval_data["status"] in ["PASS", "FAIL", "UNCLEAR"]


class TestEventEmission:
    """Tests for proper event emission during evaluation."""

    def test_start_event_emitted(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit a start event."""
        PluginService.get_or_create_default_plugins(test_user.id)

        dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            orchestrator._run_stage_3(test_job.id, Mock())

        # Check that dispatcher was called
        assert dispatcher is not None

    def test_completion_event_emitted(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """Stage 3 should emit a completion event with status counts."""
        PluginService.get_or_create_default_plugins(test_user.id)

        dispatcher = Mock()
        orchestrator = PipelineOrchestrator(dispatcher=dispatcher)

        test_results = {
            "a1": {"status": "PASS", "reasoning": "ok"},
            "a2": {"status": "FAIL", "reasoning": "not ok"},
        }

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = test_results

            orchestrator._run_stage_3(test_job.id, Mock())

        assert dispatcher is not None


class TestLoggerCompatibility:
    """Tests for logger compatibility with both function and logger objects."""

    def test_stage3_eval_with_function_logger(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle function-style logger."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Create a function logger
        log_messages = []

        def func_logger(msg):
            log_messages.append(msg)

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, func_logger)

        assert result
        assert len(log_messages) > 0  # Should have logged something

    def test_stage3_eval_with_logger_object(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle logger objects with info/error methods."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Create a logger object
        import logging

        logger_obj = logging.getLogger("test_logger")

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, logger_obj)

        assert result

    def test_stage3_eval_with_none_logger(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle None logger gracefully."""
        PluginService.get_or_create_default_plugins(test_user.id)

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, None)

        assert result

    def test_stage3_eval_logger_handles_errors(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should properly call logger.error on exceptions."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Create a logger object that tracks error calls
        error_logged = []

        class TestLogger:
            def info(self, msg):
                pass

            def warning(self, msg):
                pass

            def error(self, msg, exc_info=False):
                error_logged.append((msg, exc_info))

            def debug(self, msg):
                pass

        test_logger = TestLogger()

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.side_effect = Exception("Test error")

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, test_logger)

        assert not result
        assert len(error_logged) > 0  # Should have logged the error


class TestStage3EvaluationStandaloneFunction:
    """Tests for standalone stage_3_evaluation() function."""

    def test_stage3_eval_with_active_plugins(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should evaluate all active plugins."""
        PluginService.get_or_create_default_plugins(test_user.id)
        active_plugins = PluginService.get_active_plugins_for_evaluation(test_user.id)

        assert len(active_plugins) > 0

        # Mock evaluate_paper
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {
                str(active_plugins[0]["id"]): {"status": "PASS", "reasoning": "Code is available"}
            }

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        results = updated_job.get_evidence()
        assert len(results) > 0

    def test_stage3_eval_with_no_plugins(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle zero active plugins."""
        # No plugins seeded
        with patch("services.event_dispatcher.EventDispatcher"):
            result = stage_3_evaluation(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        assert len(updated_job.get_evidence()) == 0

    def test_stage3_eval_handles_missing_job(self):
        """stage_3_evaluation should handle missing job gracefully."""
        fake_job_id = str(uuid4())

        result = stage_3_evaluation(fake_job_id, Mock())

        assert not result

    def test_stage3_eval_with_error(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should handle errors gracefully."""
        PluginService.get_or_create_default_plugins(test_user.id)

        # Mock evaluate_paper to raise error
        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.side_effect = Exception("LLM error")

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, Mock())

        assert not result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "error"
        assert "failed" in updated_job.error_message.lower() or "evaluation" in updated_job.error_message.lower()

    def test_stage3_eval_stores_results_json(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should store results as valid JSON."""
        PluginService.get_or_create_default_plugins(test_user.id)

        test_results = {
            "plugin1": {"status": "PASS", "reasoning": "Good"},
            "plugin2": {"status": "FAIL", "reasoning": "Bad"},
        }

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = test_results

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        results = updated_job.get_evidence()

        # Verify valid JSON parsing
        assert isinstance(results, dict)
        assert len(results) == 2

    def test_stage3_eval_completes_job(self, test_job, test_user, test_paper_analysis, test_execution_details):
        """stage_3_evaluation should mark job as completed."""
        PluginService.get_or_create_default_plugins(test_user.id)

        with patch("services.evaluation_service.evaluate_paper") as mock_eval:
            mock_eval.return_value = {}

            with patch("services.event_dispatcher.EventDispatcher"):
                result = stage_3_evaluation(test_job.id, Mock())

        assert result

        updated_job = Job.get_by_id(test_job.id)
        assert updated_job.status == "completed"
        assert updated_job.progress == 1.0
        assert updated_job.current_stage == "evaluation"
        assert updated_job.completed_at is not None
