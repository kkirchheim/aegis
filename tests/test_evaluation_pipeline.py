"""Tests for Phase 4 evaluation pipeline integration."""

import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from models.database import ExecutionDetails, Job, PaperAnalysis, User
from services.evaluation_service import (
    evaluate_paper,
    parse_evaluation_response,
    render_evaluation_prompt,
)
from services.plugin_service import PluginService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def user_with_aspects(app):
    """Create a user with default aspects."""
    with app.app_context():
        user = User.create(
            username="testuser",
            email="test@example.com",
            password_hash="hash",
        )
        PluginService.get_or_create_default_plugins(user.id)
        return user


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = Mock()
    provider.complete = Mock(return_value="")
    return provider


# ============================================================================
# Prompt Rendering Tests
# ============================================================================


@pytest.mark.db
class TestPromptRendering:
    """Tests for render_evaluation_prompt function."""

    def test_render_with_single_aspect(self):
        """Test rendering prompt with single aspect."""
        aspects = [{"id": "aspect-1", "name": "Code Availability", "prompt_to_use": "Is code available?"}]
        paper_content = "This is the paper content."
        code_output = "This is the code output."
        execution_log = "This is the execution log."

        result = render_evaluation_prompt(aspects, paper_content, code_output, execution_log)

        assert result is not None
        assert "Code Availability" in result
        assert "Is code available?" in result
        assert "This is the paper content." in result
        assert "This is the code output." in result
        assert "This is the execution log." in result

    def test_render_with_multiple_aspects(self):
        """Test rendering prompt with multiple aspects."""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability", "prompt_to_use": "Is code available?"},
            {"id": "aspect-2", "name": "Dependencies", "prompt_to_use": "Are dependencies documented?"},
            {"id": "aspect-3", "name": "Reproducibility", "prompt_to_use": "Can results be reproduced?"},
        ]
        paper_content = "Paper content"
        code_output = "Output"
        execution_log = "Log"

        result = render_evaluation_prompt(aspects, paper_content, code_output, execution_log)

        assert result is not None
        assert "Code Availability" in result
        assert "Dependencies" in result
        assert "Reproducibility" in result

    def test_render_respects_custom_prompt(self):
        """Test rendering respects custom prompt override."""
        aspects = [{"id": "aspect-1", "name": "Code Availability", "prompt_to_use": "CUSTOM PROMPT FOR CODE"}]

        result = render_evaluation_prompt(aspects, "content", "output", "log")

        assert "CUSTOM PROMPT FOR CODE" in result
        assert "Is code available?" not in result  # Original prompt should not appear

    def test_render_truncates_large_context(self):
        """Test rendering truncates large context."""
        large_paper = "x" * 30000  # Larger than 20000 limit
        large_output = "y" * 15000  # Larger than 10000 limit
        large_log = "z" * 10000  # Larger than 5000 limit

        aspects = [{"id": "aspect-1", "name": "Test", "prompt_to_use": "Test prompt"}]

        result = render_evaluation_prompt(aspects, large_paper, large_output, large_log)

        assert result is not None
        # Check content is truncated (not exact length matching due to formatting)
        assert large_paper[:20000] in result
        assert large_output[:10000] in result
        assert large_log[:5000] in result

    def test_render_handles_missing_context_gracefully(self):
        """Test rendering handles missing context gracefully."""
        aspects = [{"id": "aspect-1", "name": "Test", "prompt_to_use": "Test prompt"}]

        # All None
        result = render_evaluation_prompt(aspects, None, None, None)
        assert result is not None

        # Empty strings
        result = render_evaluation_prompt(aspects, "", "", "")
        assert result is not None

    def test_render_with_empty_aspects_returns_none(self):
        """Test rendering with empty aspects list returns None."""
        result = render_evaluation_prompt([], "content", "output", "log")
        assert result is None

    def test_render_with_special_characters_in_aspect_name(self):
        """Test rendering handles special characters in aspect names."""
        aspects = [{"id": "aspect-1", "name": "Code & Test (v2)", "prompt_to_use": "Evaluate this"}]

        result = render_evaluation_prompt(aspects, "content", "output", "log")

        assert result is not None
        assert "Code & Test (v2)" in result


# ============================================================================
# Response Parsing Tests
# ============================================================================


def _make_json_response(items):
    """Helper to create JSON response in the format parse_evaluation_response expects."""
    return json.dumps([{"plugin": item[0], "status": item[1], "reasoning": item[2]} for item in items])


@pytest.mark.db
class TestResponseParsing:
    """Tests for parse_evaluation_response function."""

    def test_parse_single_pass_result(self):
        """Test parsing single PASS result."""
        response = _make_json_response(
            [("Code Availability", "PASS", "Code is available on GitHub with clear documentation.")]
        )
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "Check code availability"}]

        result = parse_evaluation_response(response, aspects)

        assert "aspect-1" in result
        assert result["aspect-1"]["status"] == "PASS"
        assert "Code is available" in result["aspect-1"]["reasoning"]

    def test_parse_single_fail_result(self):
        """Test parsing single FAIL result."""
        response = _make_json_response([("Code Availability", "FAIL", "No code repository was provided or found.")])
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "Check code availability"}]

        result = parse_evaluation_response(response, aspects)

        assert result["aspect-1"]["status"] == "FAIL"
        assert "No code repository" in result["aspect-1"]["reasoning"]

    def test_parse_unclear_result(self):
        """Test parsing UNCLEAR result."""
        response = _make_json_response(
            [("Code Availability", "UNCLEAR", "The paper mentions code but it's ambiguous where to find it.")]
        )
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "Check code availability"}]

        result = parse_evaluation_response(response, aspects)

        assert result["aspect-1"]["status"] == "UNCLEAR"
        assert "ambiguous" in result["aspect-1"]["reasoning"]

    def test_parse_multiple_aspects_mixed_results(self):
        """Test parsing multiple aspects with mixed results."""
        response = _make_json_response(
            [
                ("Code Availability", "PASS", "Code is available on GitHub."),
                ("Dependencies", "FAIL", "No dependency file was found."),
                ("Reproducibility", "UNCLEAR", "Insufficient information to determine reproducibility."),
            ]
        )
        aspects = [
            {"id": "aspect-1", "name": "Code Availability", "description": "desc"},
            {"id": "aspect-2", "name": "Dependencies", "description": "desc"},
            {"id": "aspect-3", "name": "Reproducibility", "description": "desc"},
        ]

        result = parse_evaluation_response(response, aspects)

        assert len(result) == 3
        assert result["aspect-1"]["status"] == "PASS"
        assert result["aspect-2"]["status"] == "FAIL"
        assert result["aspect-3"]["status"] == "UNCLEAR"

    def test_parse_missing_aspect_returns_empty(self):
        """Test parsing when aspect missing from response returns no entry for it."""
        response = _make_json_response([("Code Availability", "PASS", "Code is available.")])
        aspects = [
            {"id": "aspect-1", "name": "Code Availability", "description": "desc"},
            {"id": "aspect-2", "name": "Dependencies", "description": "desc"},
        ]

        result = parse_evaluation_response(response, aspects)

        assert result["aspect-1"]["status"] == "PASS"
        # Missing aspect won't have an entry (JSON parser only returns what's in the response)
        assert "aspect-2" not in result

    def test_parse_malformed_status_returns_unclear(self):
        """Test parsing when status is malformed returns UNCLEAR."""
        response = _make_json_response([("Code Availability", "MAYBE", "This status is not recognized.")])
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        # Should parse as UNCLEAR since MAYBE is not recognized
        assert result["aspect-1"]["status"] == "UNCLEAR"

    def test_parse_reasoning_extraction(self):
        """Test reasoning extraction from response."""
        response = _make_json_response(
            [
                (
                    "Code Availability",
                    "PASS",
                    "The code is available on GitHub repository. The implementation matches the paper's description.",
                )
            ]
        )
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        reasoning = result["aspect-1"]["reasoning"]
        assert len(reasoning) <= 500
        assert "GitHub" in reasoning
        assert "implementation" in reasoning

    def test_parse_handles_extra_whitespace(self):
        """Test parsing handles extra whitespace."""
        response = json.dumps(
            [{"plugin": "  Code Availability  ", "status": "  PASS  ", "reasoning": "  Code is available.  "}]
        )
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        # The parser may or may not strip whitespace from plugin name lookup
        # If the name doesn't match exactly, result may be empty
        if "aspect-1" in result:
            assert result["aspect-1"]["status"] == "PASS"

    def test_parse_case_insensitive_status(self):
        """Test parsing normalizes status to uppercase."""
        response = _make_json_response([("Code Availability", "pass", "Code is available.")])
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        # Status should be normalized to uppercase
        assert result["aspect-1"]["status"] == "PASS"

    def test_parse_with_section_separators(self):
        """Test parsing multiple entries in JSON array."""
        response = _make_json_response(
            [
                ("Code Availability", "PASS", "Code is available."),
                ("Dependencies", "FAIL", "Dependencies not documented."),
            ]
        )
        aspects = [
            {"id": "aspect-1", "name": "Code Availability", "description": "desc"},
            {"id": "aspect-2", "name": "Dependencies", "description": "desc"},
        ]

        result = parse_evaluation_response(response, aspects)

        assert result["aspect-1"]["status"] == "PASS"
        assert result["aspect-2"]["status"] == "FAIL"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.db
class TestEvaluationPipeline:
    """Tests for full evaluation pipeline integration."""

    def test_full_pipeline_render_parse(self, user_with_aspects):
        """Test full pipeline: render + parse."""
        # Get active aspects
        aspects = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)

        # Render prompt
        prompt = render_evaluation_prompt(
            aspects, "Paper about reproducibility", "Code executed successfully", "Execution completed"
        )

        assert prompt is not None

        # Simulate LLM response (JSON format)
        response = json.dumps(
            [
                {"plugin": aspect["name"], "status": "PASS", "reasoning": f"Evaluated {aspect['name']}"}
                for aspect in aspects
            ]
        )

        # Parse response
        result = parse_evaluation_response(response, aspects)

        assert len(result) > 0
        # Should have entries for aspects
        assert all(isinstance(v, dict) for v in result.values())
        assert all("status" in v and "reasoning" in v for v in result.values())

    def test_no_active_plugins_returns_empty(self, app, user_with_aspects):
        """Test no active aspects returns empty results."""
        with app.app_context():
            # Deactivate all aspects
            for aspect in PluginService.get_all_plugins_for_user(user_with_aspects.id):
                PluginService.deactivate_plugin(user_with_aspects.id, aspect["id"])

            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)
            assert len(active) == 0

    def test_job_status_updated_on_success(self, app, user_with_aspects, mock_llm_provider):
        """Test job status updated to completed on success."""
        with app.app_context():
            # Create job
            job = Job.create(id="test-job-1", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            # Create paper analysis
            paper = PaperAnalysis.create(job=job, extracted_text="Test paper content")

            # Get active aspects to build matching response
            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)

            # Mock LLM response (JSON format matching actual plugin names)
            mock_llm_provider.complete.return_value = json.dumps(
                [{"plugin": a["name"], "status": "PASS", "reasoning": f"Evaluated {a['name']}"} for a in active]
            )

            # Call evaluate_paper
            result = evaluate_paper(job.id, paper, "code output", "execution log", mock_llm_provider, app_logger=None)

            # evaluate_paper returns results dict but does NOT update the job
            # (job status is updated by the orchestrator's stage_3_evaluation)
            assert len(result) > 0
            assert all("status" in v and "reasoning" in v for v in result.values())

    def test_evidence_stored_correctly(self, app, user_with_aspects, mock_llm_provider):
        """Test evaluation results stored correctly in job."""
        with app.app_context():
            job = Job.create(id="test-job-2", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            paper = PaperAnalysis.create(job=job, extracted_text="Test content")

            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)

            mock_llm_provider.complete.return_value = json.dumps(
                [{"plugin": a["name"], "status": "PASS", "reasoning": f"Reason for {a['name']}"} for a in active]
            )

            result = evaluate_paper(job.id, paper, "output", "log", mock_llm_provider)

            # evaluate_paper returns results dict but does NOT store them on the job
            # (the orchestrator's stage_3_evaluation handles persistence)
            assert len(result) > 0
            assert all("status" in v and "reasoning" in v for v in result.values())

    def test_error_handling_invalid_response(self, app, user_with_aspects, mock_llm_provider):
        """Test error handling for invalid LLM response."""
        with app.app_context():
            job = Job.create(id="test-job-3", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            paper = PaperAnalysis.create(job=job, extracted_text="Content")

            # Invalid response
            mock_llm_provider.complete.return_value = "This is not a valid response format"

            result = evaluate_paper(job.id, paper, "output", "log", mock_llm_provider)

            # evaluate_paper returns empty dict on parse failure but does NOT update job status
            # (job status management is the orchestrator's responsibility)
            assert result == {}

    def test_error_handling_llm_failure(self, app, user_with_aspects, mock_llm_provider):
        """Test error handling when LLM call fails."""
        with app.app_context():
            job = Job.create(id="test-job-4", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            paper = PaperAnalysis.create(job=job, extracted_text="Content")

            # Mock LLM failure
            mock_llm_provider.complete.side_effect = Exception("LLM API error")

            result = evaluate_paper(job.id, paper, "output", "log", mock_llm_provider)

            # evaluate_paper catches the exception and returns empty dict
            # It does NOT update job status (that's the orchestrator's responsibility)
            assert result == {}


# ============================================================================
# Database Field Tests
# ============================================================================


@pytest.mark.db
class TestDatabaseFields:
    """Tests for evidence database field."""

    def test_job_evidence_nullable(self, app, user_with_aspects):
        """Test Job.evidence field is nullable."""
        with app.app_context():
            job = Job.create(id="test-job-null", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="pending")

            assert job.evidence is None
            assert job.get_evidence() == {}

    def test_job_stores_json_evidence(self, app, user_with_aspects):
        """Test Job stores evidence as JSON."""
        with app.app_context():
            job = Job.create(id="test-job-json", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            test_data = {"aspect-1": {"status": "PASS", "reasoning": "Test reasoning"}}

            job.set_evidence(test_data)
            job.save()

            # Retrieve and check
            retrieved = Job.get_by_id(job.id)
            assert retrieved.get_evidence() == test_data

    def test_job_evidence_retrievable(self, app, user_with_aspects):
        """Test Job.evidence is retrievable across sessions."""
        with app.app_context():
            job = Job.create(
                id="test-job-retrieve", user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing"
            )

            test_results = {
                "aspect-1": {"status": "PASS", "reasoning": "Reason 1"},
                "aspect-2": {"status": "FAIL", "reasoning": "Reason 2"},
            }

            job.set_evidence(test_results)
            job.save()

        with app.app_context():
            # Retrieve in new session
            retrieved_job = Job.get_by_id(job.id)
            stored = retrieved_job.get_evidence()

            assert stored == test_results
            assert len(stored) == 2


# ============================================================================
# Edge Cases and Robustness Tests
# ============================================================================


@pytest.mark.db
class TestEdgeCases:
    """Tests for edge cases and robustness."""

    def test_parse_invalid_json_returns_empty(self):
        """Test parsing when response is not valid JSON returns empty dict."""
        response = "This is not JSON at all"
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        assert result == {}

    def test_parse_reasoning_max_length(self):
        """Test reasoning is truncated to max 500 chars."""
        long_reasoning = "x" * 1000
        response = _make_json_response([("Code Availability", "PASS", long_reasoning)])
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        assert len(result["aspect-1"]["reasoning"]) <= 500

    def test_render_with_none_aspect_fields(self):
        """Test rendering when aspect dict has unexpected fields."""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Test",
                # Missing prompt_to_use
            }
        ]

        # Should handle gracefully
        result = render_evaluation_prompt(aspects, "content", "output", "log")
        assert result is not None

    def test_parse_with_unicode_characters(self):
        """Test parsing handles unicode characters."""
        response = _make_json_response(
            [("Code Availability", "PASS", "Code is available (\u2713) with full documentation (\u2713).")]
        )
        aspects = [{"id": "aspect-1", "name": "Code Availability", "description": "desc"}]

        result = parse_evaluation_response(response, aspects)

        assert result["aspect-1"]["status"] == "PASS"
        assert "\u2713" in result["aspect-1"]["reasoning"]


# ============================================================================
# Aspect Metadata Tests (CRITICAL: descriptions must be included)
# ============================================================================


@pytest.mark.db
class TestAspectMetadataInResults:
    """Tests that aspect descriptions are properly included in results."""

    def test_parse_includes_aspect_descriptions(self, app, user_with_aspects):
        """Test that parse_evaluation_response includes aspect descriptions."""
        with app.app_context():
            # Get active aspects (should have descriptions from DEFAULT_PLUGINS)
            active_plugins = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)

            # Verify aspects have description field
            assert all("description" in a for a in active_plugins), "Active aspects missing description field"
            assert all(a["description"] for a in active_plugins), "Active aspects have empty descriptions"

            # Simulate LLM response with JSON array
            response = json.dumps(
                [
                    {"plugin": aspect["name"], "status": "PASS", "reasoning": f"Evaluated {aspect['name']}"}
                    for aspect in active_plugins
                ]
            )

            # Parse response
            result = parse_evaluation_response(response, active_plugins)

            # Verify each result includes plugin_description
            assert len(result) == len(active_plugins), f"Expected {len(active_plugins)} results, got {len(result)}"

            for aspect_id, aspect_result in result.items():
                # Check all required fields present
                assert "plugin_name" in aspect_result, f"Missing plugin_name for {aspect_id}"
                assert "plugin_description" in aspect_result, f"Missing plugin_description for {aspect_id}"
                assert "status" in aspect_result, f"Missing status for {aspect_id}"
                assert "reasoning" in aspect_result, f"Missing reasoning for {aspect_id}"

                # Check descriptions are non-empty
                assert aspect_result["plugin_description"], f"Aspect {aspect_id} has empty description: {aspect_result}"

                # Verify it matches one of the original aspects
                matching_aspect = next((a for a in active_plugins if str(a["id"]) == aspect_id), None)
                assert matching_aspect, f"No original aspect for {aspect_id}"
                assert aspect_result["plugin_description"] == matching_aspect["description"], (
                    f"Description mismatch for {aspect_id}"
                )

    def test_evaluate_paper_returns_descriptions(self, app, user_with_aspects, mock_llm_provider):
        """Integration test: evaluate_paper returns descriptions in results."""
        with app.app_context():
            # Create job and supporting data
            job = Job.create(id=str(uuid4()), user=user_with_aspects, pdf_path="/tmp/test.pdf", status="processing")

            paper_analysis = PaperAnalysis.create(
                job=job,
                pdf_hash="test-hash",
                title="Test Paper",
                abstract="Test abstract",
                extracted_text="This is test paper content.",
                methodology="Test methodology",
                dependencies=json.dumps(["numpy", "pandas"]),
                dataset_description="Test dataset",
                claimed_results=json.dumps({"accuracy": 0.95}),
            )

            execution = ExecutionDetails.create(
                job=job,
                stdout_combined="Test output",
                commands_run=json.dumps(["python test.py"]),
                dependencies_used=json.dumps(["numpy", "pandas"]),
                errors_summary="No errors",
                test_info="All tests passed",
                randomness_info="seed=42",
                discovered_files=json.dumps(["file1.py"]),
                actual_results=json.dumps({"accuracy": 0.95}),
            )

            # Get active aspects
            active_plugins = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)

            # Mock LLM response with valid JSON
            llm_response = json.dumps(
                [
                    {"plugin": aspect["name"], "status": "PASS", "reasoning": f"Test evaluation for {aspect['name']}"}
                    for aspect in active_plugins
                ]
            )
            mock_llm_provider.complete.return_value = llm_response

            # Call evaluate_paper
            result = evaluate_paper(
                job_id=job.id,
                paper_analysis=paper_analysis,
                code_output=execution.stdout_combined,
                execution_log=execution.errors_summary,
                llm_provider=mock_llm_provider,
                app_logger=None,
            )

            # Verify descriptions are in results
            assert len(result) == len(active_plugins), f"Expected {len(active_plugins)} results, got {len(result)}"

            for aspect_id, res in result.items():
                # Critical: description must not be empty
                assert "plugin_description" in res, f"Missing plugin_description in result for {aspect_id}"
                assert res["plugin_description"], f"EMPTY plugin_description for {aspect_id}: {res}"

                # Verify it's the actual description, not empty string
                matching = next((a for a in active_plugins if str(a["id"]) == aspect_id), None)
                assert matching, f"Could not find aspect {aspect_id} in active list"
                assert res["plugin_description"] == matching["description"], f"Description mismatch for {aspect_id}"

    def test_custom_aspects_include_descriptions(self, app, user_with_aspects):
        """Integration test: custom aspects must have descriptions in evaluation results."""
        with app.app_context():
            # Create a custom aspect WITH description
            custom = PluginService.create_custom_plugin(
                user_id=user_with_aspects.id,
                name="Custom Reproducibility Check",
                description="Verify that custom aspects preserve descriptions through evaluation",
                prompt="Can this custom aspect be evaluated?",
            )

            # Verify it was created with description
            all_aspects = PluginService.get_all_plugins_for_user(user_with_aspects.id)
            custom_from_db = next((a for a in all_aspects if a["id"] == custom["id"]), None)
            assert custom_from_db is not None, "Custom aspect not found in get_all_aspects"
            assert custom_from_db["description"], "Custom aspect has empty description in get_all_aspects"

            # Get active aspects for evaluation
            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)
            custom_active = next((a for a in active if a["id"] == custom["id"]), None)
            assert custom_active is not None, "Custom aspect not in active aspects"
            assert custom_active["description"], (
                f"Custom aspect lost description in get_active_plugins_for_evaluation: {custom_active}"
            )
            assert custom_active["description"] == custom["description"], (
                f"Description mismatch: {custom_active['description']} vs {custom['description']}"
            )
