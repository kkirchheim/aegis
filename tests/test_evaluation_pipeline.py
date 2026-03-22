"""Tests for Phase 4 evaluation pipeline integration."""

import pytest
import json
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from models.database import User, Job, PaperAnalysis, ExecutionDetails
from models.plugin import Aspect, UserPlugin
from services.evaluation_service import (
    render_evaluation_prompt,
    parse_evaluation_response,
    evaluate_paper,
)
from services.plugin_service import PluginService
from repositories.plugin_repository import AspectRepository, UserPluginRepository


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
        PluginService.get_or_create_default_aspects(user.id)
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
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability",
                "prompt_to_use": "Is code available?"
            }
        ]
        paper_content = "This is the paper content."
        code_output = "This is the code output."
        execution_log = "This is the execution log."
        
        result = render_evaluation_prompt(
            aspects, paper_content, code_output, execution_log
        )
        
        assert result is not None
        assert "Code Availability" in result
        assert "Is code available?" in result
        assert "This is the paper content." in result
        assert "This is the code output." in result
        assert "This is the execution log." in result
    
    def test_render_with_multiple_aspects(self):
        """Test rendering prompt with multiple aspects."""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability",
                "prompt_to_use": "Is code available?"
            },
            {
                "id": "aspect-2",
                "name": "Dependencies",
                "prompt_to_use": "Are dependencies documented?"
            },
            {
                "id": "aspect-3",
                "name": "Reproducibility",
                "prompt_to_use": "Can results be reproduced?"
            }
        ]
        paper_content = "Paper content"
        code_output = "Output"
        execution_log = "Log"
        
        result = render_evaluation_prompt(
            aspects, paper_content, code_output, execution_log
        )
        
        assert result is not None
        assert "Code Availability" in result
        assert "Dependencies" in result
        assert "Reproducibility" in result
        assert result.count("###") >= 3  # At least 3 aspect headers
    
    def test_render_respects_custom_prompt(self):
        """Test rendering respects custom prompt override."""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability",
                "prompt_to_use": "CUSTOM PROMPT FOR CODE"
            }
        ]
        
        result = render_evaluation_prompt(
            aspects, "content", "output", "log"
        )
        
        assert "CUSTOM PROMPT FOR CODE" in result
        assert "Is code available?" not in result  # Original prompt should not appear
    
    def test_render_truncates_large_context(self):
        """Test rendering truncates large context."""
        large_paper = "x" * 30000  # Larger than 20000 limit
        large_output = "y" * 15000  # Larger than 10000 limit
        large_log = "z" * 10000  # Larger than 5000 limit
        
        aspects = [
            {
                "id": "aspect-1",
                "name": "Test",
                "prompt_to_use": "Test prompt"
            }
        ]
        
        result = render_evaluation_prompt(
            aspects, large_paper, large_output, large_log
        )
        
        assert result is not None
        # Check content is truncated (not exact length matching due to formatting)
        assert large_paper[:20000] in result
        assert large_output[:10000] in result
        assert large_log[:5000] in result
    
    def test_render_handles_missing_context_gracefully(self):
        """Test rendering handles missing context gracefully."""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Test",
                "prompt_to_use": "Test prompt"
            }
        ]
        
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
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code & Test (v2)",
                "prompt_to_use": "Evaluate this"
            }
        ]
        
        result = render_evaluation_prompt(
            aspects, "content", "output", "log"
        )
        
        assert result is not None
        assert "Code & Test (v2)" in result


# ============================================================================
# Response Parsing Tests
# ============================================================================

@pytest.mark.db
class TestResponseParsing:
    """Tests for parse_evaluation_response function."""
    
    def test_parse_single_pass_result(self):
        """Test parsing single PASS result."""
        response = """
### Code Availability
Status: PASS
Reasoning: Code is available on GitHub with clear documentation.
"""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability"
            }
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "PASS"
        assert "Code is available" in result["aspect-1"]["reasoning"]
    
    def test_parse_single_fail_result(self):
        """Test parsing single FAIL result."""
        response = """
### Code Availability
Status: FAIL
Reasoning: No code repository was provided or found.
"""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability"
            }
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "FAIL"
        assert "No code repository" in result["aspect-1"]["reasoning"]
    
    def test_parse_unclear_result(self):
        """Test parsing UNCLEAR result."""
        response = """
### Code Availability
Status: UNCLEAR
Reasoning: The paper mentions code but it's ambiguous where to find it.
"""
        aspects = [
            {
                "id": "aspect-1",
                "name": "Code Availability"
            }
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "UNCLEAR"
        assert "ambiguous" in result["aspect-1"]["reasoning"]
    
    def test_parse_multiple_aspects_mixed_results(self):
        """Test parsing multiple aspects with mixed results."""
        response = """
### Code Availability
Status: PASS
Reasoning: Code is available on GitHub.

### Dependencies
Status: FAIL
Reasoning: No dependency file was found.

### Reproducibility
Status: UNCLEAR
Reasoning: Insufficient information to determine reproducibility.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"},
            {"id": "aspect-2", "name": "Dependencies"},
            {"id": "aspect-3", "name": "Reproducibility"},
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert len(result) == 3
        assert result["aspect-1"]["status"] == "PASS"
        assert result["aspect-2"]["status"] == "FAIL"
        assert result["aspect-3"]["status"] == "UNCLEAR"
    
    def test_parse_missing_aspect_returns_unclear(self):
        """Test parsing when aspect missing from response returns UNCLEAR."""
        response = """
### Code Availability
Status: PASS
Reasoning: Code is available.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"},
            {"id": "aspect-2", "name": "Dependencies"},  # Missing from response
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "PASS"
        assert result["aspect-2"]["status"] == "UNCLEAR"
        assert "did not include evaluation" in result["aspect-2"]["reasoning"]
    
    def test_parse_malformed_status_returns_unclear(self):
        """Test parsing when status is malformed returns UNCLEAR."""
        response = """
### Code Availability
Status: MAYBE
Reasoning: This status is not recognized.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        # Should parse as UNCLEAR since MAYBE is not recognized
        assert result["aspect-1"]["status"] == "UNCLEAR"
    
    def test_parse_reasoning_extraction(self):
        """Test reasoning extraction from response."""
        response = """
### Code Availability
Status: PASS
Reasoning: The code is available on GitHub repository. The implementation matches the paper's description.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        reasoning = result["aspect-1"]["reasoning"]
        assert len(reasoning) <= 500
        assert "GitHub" in reasoning
        assert "implementation" in reasoning
    
    def test_parse_handles_extra_whitespace(self):
        """Test parsing handles extra whitespace."""
        response = """
###   Code Availability   
Status:    PASS
Reasoning:    Code is available.    
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "PASS"
        assert len(result["aspect-1"]["reasoning"].strip()) > 0
    
    def test_parse_case_insensitive_status(self):
        """Test parsing is case insensitive for status."""
        response = """
### Code Availability
Status: pass
Reasoning: Code is available.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        # Status should be normalized to uppercase
        assert result["aspect-1"]["status"] == "PASS"
    
    def test_parse_with_section_separators(self):
        """Test parsing with various section separators."""
        response = """
### Code Availability
Status: PASS
Reasoning: Code is available.

### Dependencies
Status: FAIL
Reasoning: Dependencies not documented.

### Other Aspect
Status: UNCLEAR
Reasoning: Cannot determine.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"},
            {"id": "aspect-2", "name": "Dependencies"},
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
            aspects,
            "Paper about reproducibility",
            "Code executed successfully",
            "Execution completed"
        )
        
        assert prompt is not None
        
        # Simulate LLM response
        response = f"""
### Code Availability
Status: PASS
Reasoning: Code is available on GitHub.

### Dependency Documentation
Status: FAIL
Reasoning: No requirements.txt found.

### Reproducibility
Status: UNCLEAR
Reasoning: Need more information to verify.
"""
        
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
            for aspect in PluginService.get_all_aspects_for_user(user_with_aspects.id):
                PluginService.deactivate_aspect(user_with_aspects.id, aspect["id"])
            
            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)
            assert len(active) == 0
    
    def test_job_status_updated_on_success(self, app, user_with_aspects, mock_llm_provider):
        """Test job status updated to completed on success."""
        with app.app_context():
            # Create job
            job = Job.create(
                id="test-job-1",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            # Create paper analysis
            paper = PaperAnalysis.create(
                job=job,
                extracted_text="Test paper content"
            )
            
            # Mock LLM response
            mock_llm_provider.complete.return_value = """
### Code Availability
Status: PASS
Reasoning: Code is available.

### Dependency Documentation
Status: PASS
Reasoning: Dependencies are documented.

### Reproducibility
Status: PASS
Reasoning: Results can be reproduced.
"""
            
            # Call evaluate_paper
            result = evaluate_paper(
                job.id,
                paper,
                "code output",
                "execution log",
                mock_llm_provider,
                app_logger=None
            )
            
            # Check result
            assert len(result) > 0
            
            # Check job was updated
            updated_job = Job.get_by_id(job.id)
            assert updated_job.status == "completed"
            assert updated_job.evidence is not None
    
    def test_evidence_stored_correctly(self, app, user_with_aspects, mock_llm_provider):
        """Test evaluation results stored correctly in job."""
        with app.app_context():
            job = Job.create(
                id="test-job-2",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            paper = PaperAnalysis.create(
                job=job,
                extracted_text="Test content"
            )
            
            mock_llm_provider.complete.return_value = """
### Code Availability
Status: PASS
Reasoning: Available on GitHub.

### Dependency Documentation
Status: FAIL
Reasoning: Not documented.

### Reproducibility
Status: UNCLEAR
Reasoning: Unclear.
"""
            
            result = evaluate_paper(
                job.id,
                paper,
                "output",
                "log",
                mock_llm_provider
            )
            
            # Check stored results
            updated_job = Job.get_by_id(job.id)
            stored = updated_job.get_evidence()
            
            assert len(stored) > 0
            assert all("status" in v and "reasoning" in v for v in stored.values())
    
    def test_error_handling_invalid_response(self, app, user_with_aspects, mock_llm_provider):
        """Test error handling for invalid LLM response."""
        with app.app_context():
            job = Job.create(
                id="test-job-3",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            paper = PaperAnalysis.create(
                job=job,
                extracted_text="Content"
            )
            
            # Invalid response
            mock_llm_provider.complete.return_value = "This is not a valid response format"
            
            result = evaluate_paper(
                job.id,
                paper,
                "output",
                "log",
                mock_llm_provider
            )
            
            # Should return empty dict on parse failure
            # (but still completes gracefully)
            updated_job = Job.get_by_id(job.id)
            # Job should complete even with parse issues
            assert updated_job.status in ["completed", "error"]
    
    def test_error_handling_llm_failure(self, app, user_with_aspects, mock_llm_provider):
        """Test error handling when LLM call fails."""
        with app.app_context():
            job = Job.create(
                id="test-job-4",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            paper = PaperAnalysis.create(
                job=job,
                extracted_text="Content"
            )
            
            # Mock LLM failure
            mock_llm_provider.complete.side_effect = Exception("LLM API error")
            
            result = evaluate_paper(
                job.id,
                paper,
                "output",
                "log",
                mock_llm_provider
            )
            
            # Should return empty dict
            assert result == {}
            
            # Job should be marked as error
            updated_job = Job.get_by_id(job.id)
            assert updated_job.status == "error"


# ============================================================================
# Database Field Tests
# ============================================================================

@pytest.mark.db
class TestDatabaseFields:
    """Tests for evidence database field."""
    
    def test_job_evidence_nullable(self, app, user_with_aspects):
        """Test Job.evidence field is nullable."""
        with app.app_context():
            job = Job.create(
                id="test-job-null",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="pending"
            )
            
            assert job.evidence is None
            assert job.get_evidence() == {}
    
    def test_job_stores_json_evidence(self, app, user_with_aspects):
        """Test Job stores evidence as JSON."""
        with app.app_context():
            job = Job.create(
                id="test-job-json",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            test_data = {
                "aspect-1": {
                    "status": "PASS",
                    "reasoning": "Test reasoning"
                }
            }
            
            job.set_evidence(test_data)
            job.save()
            
            # Retrieve and check
            retrieved = Job.get_by_id(job.id)
            assert retrieved.get_evidence() == test_data
    
    def test_job_evidence_retrievable(self, app, user_with_aspects):
        """Test Job.evidence is retrievable across sessions."""
        with app.app_context():
            job = Job.create(
                id="test-job-retrieve",
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
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
    
    def test_parse_with_missing_status_line(self):
        """Test parsing when status line is missing."""
        response = """
### Code Availability
Reasoning: Code is available.
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        # Should default to UNCLEAR
        assert result["aspect-1"]["status"] == "UNCLEAR"
    
    def test_parse_reasoning_max_length(self):
        """Test reasoning is truncated to max 500 chars."""
        long_reasoning = "x" * 1000
        response = f"""
### Code Availability
Status: PASS
Reasoning: {long_reasoning}
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
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
        response = """
### Code Availability
Status: PASS
Reasoning: Code is available (✓) with full documentation (✓).
"""
        aspects = [
            {"id": "aspect-1", "name": "Code Availability"}
        ]
        
        result = parse_evaluation_response(response, aspects)
        
        assert result["aspect-1"]["status"] == "PASS"
        assert "✓" in result["aspect-1"]["reasoning"]


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
            assert all("description" in a for a in active_plugins), \
                "Active aspects missing description field"
            assert all(a["description"] for a in active_plugins), \
                "Active aspects have empty descriptions"
            
            # Simulate LLM response with JSON array
            response = json.dumps([
                {
                    "aspect": aspect["name"],
                    "status": "PASS",
                    "reasoning": f"Evaluated {aspect['name']}"
                }
                for aspect in active_plugins
            ])
            
            # Parse response
            result = parse_evaluation_response(response, active_plugins)
            
            # Verify each result includes aspect_description
            assert len(result) == len(active_plugins), \
                f"Expected {len(active_plugins)} results, got {len(result)}"
            
            for aspect_id, aspect_result in result.items():
                # Check all required fields present
                assert "aspect_name" in aspect_result, f"Missing aspect_name for {aspect_id}"
                assert "aspect_description" in aspect_result, f"Missing aspect_description for {aspect_id}"
                assert "status" in aspect_result, f"Missing status for {aspect_id}"
                assert "reasoning" in aspect_result, f"Missing reasoning for {aspect_id}"
                
                # Check descriptions are non-empty
                assert aspect_result["aspect_description"], \
                    f"Aspect {aspect_id} has empty description: {aspect_result}"
                
                # Verify it matches one of the original aspects
                matching_aspect = next(
                    (a for a in active_plugins if str(a["id"]) == aspect_id),
                    None
                )
                assert matching_aspect, f"No original aspect for {aspect_id}"
                assert aspect_result["aspect_description"] == matching_aspect["description"], \
                    f"Description mismatch for {aspect_id}"
    
    def test_evaluate_paper_returns_descriptions(self, app, user_with_aspects, mock_llm_provider):
        """Integration test: evaluate_paper returns descriptions in results."""
        with app.app_context():
            # Create job and supporting data
            job = Job.create(
                id=str(uuid4()),
                user=user_with_aspects,
                pdf_path="/tmp/test.pdf",
                status="processing"
            )
            
            paper_analysis = PaperAnalysis.create(
                job=job,
                pdf_hash="test-hash",
                title="Test Paper",
                abstract="Test abstract",
                extracted_text="This is test paper content.",
                methodology="Test methodology",
                dependencies=json.dumps(["numpy", "pandas"]),
                dataset_description="Test dataset",
                claimed_results=json.dumps({"accuracy": 0.95})
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
                actual_results=json.dumps({"accuracy": 0.95})
            )
            
            # Get active aspects
            active_plugins = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)
            
            # Mock LLM response with valid JSON
            llm_response = json.dumps([
                {
                    "aspect": aspect["name"],
                    "status": "PASS",
                    "reasoning": f"Test evaluation for {aspect['name']}"
                }
                for aspect in active_plugins
            ])
            mock_llm_provider.complete.return_value = llm_response
            
            # Call evaluate_paper
            result = evaluate_paper(
                job_id=job.id,
                paper_analysis=paper_analysis,
                code_output=execution.stdout_combined,
                execution_log=execution.errors_summary,
                llm_provider=mock_llm_provider,
                app_logger=None
            )
            
            # Verify descriptions are in results
            assert len(result) == len(active_plugins), \
                f"Expected {len(active_plugins)} results, got {len(result)}"
            
            for aspect_id, res in result.items():
                # Critical: description must not be empty
                assert "aspect_description" in res, \
                    f"Missing aspect_description in result for {aspect_id}"
                assert res["aspect_description"], \
                    f"EMPTY aspect_description for {aspect_id}: {res}"
                
                # Verify it's the actual description, not empty string
                matching = next(
                    (a for a in active_plugins if str(a["id"]) == aspect_id),
                    None
                )
                assert matching, f"Could not find aspect {aspect_id} in active list"
                assert res["aspect_description"] == matching["description"], \
                    f"Description mismatch for {aspect_id}"
    
    def test_custom_aspects_include_descriptions(self, app, user_with_aspects):
        """Integration test: custom aspects must have descriptions in evaluation results."""
        with app.app_context():
            # Create a custom aspect WITH description
            custom = PluginService.create_custom_aspect(
                user_id=user_with_aspects.id,
                name="Custom Reproducibility Check",
                description="Verify that custom aspects preserve descriptions through evaluation",
                prompt="Can this custom aspect be evaluated?"
            )
            
            # Verify it was created with description
            all_aspects = PluginService.get_all_aspects_for_user(user_with_aspects.id)
            custom_from_db = next(
                (a for a in all_aspects if a["id"] == custom["id"]),
                None
            )
            assert custom_from_db is not None, "Custom aspect not found in get_all_aspects"
            assert custom_from_db["description"], "Custom aspect has empty description in get_all_aspects"
            
            # Get active aspects for evaluation
            active = PluginService.get_active_plugins_for_evaluation(user_with_aspects.id)
            custom_active = next(
                (a for a in active if a["id"] == custom["id"]),
                None
            )
            assert custom_active is not None, "Custom aspect not in active aspects"
            assert custom_active["description"], \
                f"Custom aspect lost description in get_active_plugins_for_evaluation: {custom_active}"
            assert custom_active["description"] == custom["description"], \
                f"Description mismatch: {custom_active['description']} vs {custom['description']}"
