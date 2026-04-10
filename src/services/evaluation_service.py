"""Evaluation service - reproducibility evaluation and plugin checking."""

import hashlib
import json
import re
import time
from typing import Dict, List, Optional

from config import Config
from models.database import Artifact, Job, PaperAnalysis, PluginEvaluation
from repositories import ExecutionDetailsRepository, PaperAnalysisRepository
from services.cache_service import get_cached_evaluation, store_evaluation_cache

# ============================================================================
# Logger Utility - Handle both functions and logger objects
# ============================================================================


def _log(logger, level: str, message: str):
    """
    Log a message to either a logger object or function.
    Handles both logger objects (with .info/.warning/.error methods)
    and logger functions (passed from orchestrator).
    """
    if not logger:
        return

    if callable(logger) and not hasattr(logger, level):
        # It's a function, not a logger object
        logger(f"[{level.upper()}] {message}")
    else:
        # It's a logger object
        method = getattr(logger, level, None)
        if method:
            method(message)


# ============================================================================
# Phase 4: Unified Evaluation Prompt Templates
# ============================================================================

PLUGIN_EVAL_TEMPLATE = """You are evaluating the reproducibility of a research paper across multiple dimensions.

For each plugin below, provide:
- Status: PASS / FAIL / UNCLEAR
- Reasoning: 1-2 sentences max (plain text, NO markdown formatting)

IMPORTANT: Respond with a JSON array. Do not use any markdown formatting in reasoning text.

---

PAPER CONTENT:
{paper_content}

CODE EXECUTION OUTPUT:
{code_output}

EXECUTION LOG:
{execution_log}

---

PLUGINS TO EVALUATE:
{plugins_list}

---

RESPONSE FORMAT (JSON array, ONLY valid JSON, no other text):

[
  {{"plugin": "Plugin Name", "status": "PASS|FAIL|UNCLEAR", "reasoning": "Plain text reasoning here"}},
  ...
]

PLUGINS TO EVALUATE AND RESPOND TO:
"""

PLUGIN_TEMPLATE = """{plugin_name}: {plugin_prompt}
"""


# ============================================================================
# Phase 4: Unified Evaluation Pipeline Functions
# ============================================================================


def render_evaluation_prompt(
    plugins: List[Dict[str, str]],
    paper_content: str,
    code_output: str,
    execution_log: str,
) -> Optional[str]:
    """
    Merge all active plugins into single evaluation prompt.

    Args:
        plugins: List[{id, name, prompt_to_use}] - from PluginService.get_active_plugins_for_evaluation()
        paper_content: str - Content from paper analysis
        code_output: str - Output from code execution
        execution_log: str - Log from code execution

    Returns:
        str - Full prompt ready for LLM, or None if no plugins
    """
    if not plugins:
        return None

    # Build plugins section (simple list format for JSON response)
    plugins_text = ""
    for plugin in plugins:
        prompt_to_use = plugin.get("prompt_to_use", plugin.get("prompt", ""))
        plugins_text += PLUGIN_TEMPLATE.format(plugin_name=plugin["name"], plugin_prompt=prompt_to_use)

    # Render full prompt with context (truncate to reasonable sizes)
    full_prompt = PLUGIN_EVAL_TEMPLATE.format(
        paper_content=paper_content[:20000] if paper_content else "",
        code_output=code_output[:10000] if code_output else "",
        execution_log=execution_log[:5000] if execution_log else "",
        plugins_list=plugins_text,
    )

    return full_prompt


def parse_evaluation_response(
    response_text: str,
    plugins: List[Dict[str, str]],
    logger=None,
) -> Dict[str, Dict[str, str]]:
    """
    Parse LLM JSON response into per-plugin results.

    Expected format (JSON array):
    [
      {"plugin": "Code Availability", "status": "PASS", "reasoning": "..."},
      {"plugin": "Dependency Documentation", "status": "FAIL", "reasoning": "..."},
      ...
    ]

    Args:
        response_text: str - Response from LLM (JSON)
        plugins: List[{id, name, ...}] - Same plugins that were evaluated
        logger: Optional logger (function or logger object)

    Returns:
        dict: {plugin_id: {status, reasoning}} or empty dict if parsing fails
    """
    results = {}

    # Create lookup map: plugin name -> plugin id
    plugin_lookup = {plugin["name"]: str(plugin["id"]) for plugin in plugins}

    try:
        # Extract JSON from response (handle wrapped ```json blocks)
        json_text = response_text.strip()

        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        # Parse JSON
        parsed = json.loads(json_text)

        # Handle both array and object with "evaluations" key
        if isinstance(parsed, dict) and "evaluations" in parsed:
            items = parsed["evaluations"]
        elif isinstance(parsed, list):
            items = parsed
        else:
            if logger:
                _log(logger, "error", "[PARSE] Invalid JSON structure: expected array or object with 'evaluations' key")
            return results

        # Process each evaluation item
        for item in items:
            plugin_name = item.get("plugin") or item.get("name")
            status = (item.get("status") or "UNCLEAR").upper()
            reasoning = item.get("reasoning", "")

            # Validate status
            if status not in ["PASS", "FAIL", "UNCLEAR"]:
                status = "UNCLEAR"

            # Find plugin ID by name
            plugin_id = plugin_lookup.get(plugin_name)

            if not plugin_id:
                if logger:
                    _log(logger, "warning", f"[PARSE] Unknown plugin name: {plugin_name}")
                continue

            # Find full plugin info (name, description, etc.)
            plugin_info = next((p for p in plugins if str(p["id"]) == plugin_id), None)
            plugin_display_name = plugin_info.get("name", plugin_name) if plugin_info else plugin_name
            plugin_description = plugin_info.get("description", "") if plugin_info else ""

            # Clean up markdown formatting from reasoning (if any)
            reasoning = reasoning.lstrip("* ")
            reasoning = re.sub(r"\s*-+\s*$", "", reasoning)
            reasoning = reasoning[:500]  # Max 500 chars

            results[plugin_id] = {
                "plugin_name": plugin_display_name,
                "plugin_description": plugin_description,
                "status": status,
                "reasoning": reasoning,
            }

            # Log result
            if logger:
                if status == "PASS":
                    _log(logger, "info", f"[PARSE] {plugin_name}: PASS")
                elif status == "FAIL":
                    _log(logger, "warning", f"[PARSE] {plugin_name}: FAIL - {reasoning[:100]}")
                else:
                    _log(logger, "info", f"[PARSE] {plugin_name}: {status}")

        return results

    except json.JSONDecodeError as e:
        if logger:
            _log(logger, "error", f"[PARSE] JSON decode error: {str(e)}")
            _log(logger, "error", f"[PARSE] Response text: {response_text[:500]}")
        return results
    except Exception as e:
        if logger:
            _log(logger, "error", f"[PARSE] Parsing error: {str(e)}")
        return results


def evaluate_paper(
    job_id: str,
    paper_analysis: PaperAnalysis,
    code_output: str,
    execution_log: str,
    llm_provider,
    app_logger=None,
) -> Dict[str, Dict[str, str]]:
    """
    Single LLM call to evaluate all active plugins.

    Args:
        job_id: str - Job ID
        paper_analysis: PaperAnalysis - Paper analysis result
        code_output: str - Code execution output
        execution_log: str - Code execution log
        llm_provider: LLM provider instance
        app_logger: Optional logger

    Returns:
        dict: evidence {plugin_id: {status, reasoning}}
    """
    from services.plugin_service import PluginService

    try:
        job = Job.get_by_id(job_id)

        # Get active plugins for this user
        plugins = PluginService.get_active_plugins_for_evaluation(job.user.id)

        if not plugins:
            if app_logger:
                app_logger.warning(f"[Job {job_id}] No active plugins for user {job.user.id}, skipping evaluation")
            return {}

        # Get paper content
        paper_content = paper_analysis.extracted_text or ""

        # Render unified prompt
        prompt = render_evaluation_prompt(plugins, paper_content, code_output, execution_log)

        if not prompt:
            if app_logger:
                app_logger.error(f"[Job {job_id}] Failed to render evaluation prompt")
            return {}

        # Single LLM call
        if app_logger:
            app_logger.info(f"[Job {job_id}] Calling LLM for evaluation ({len(plugins)} plugins)")

        response = llm_provider.complete(messages=[{"role": "user", "content": prompt}], max_tokens=3000)

        # Parse response with detailed logging
        evidence = parse_evaluation_response(response, plugins, logger=app_logger)

        # Log summary
        passed = sum(1 for r in evidence.values() if r.get("status") == "PASS")
        failed = sum(1 for r in evidence.values() if r.get("status") == "FAIL")
        unclear = sum(1 for r in evidence.values() if r.get("status") == "UNCLEAR")
        if app_logger:
            app_logger.info(f"[Job {job_id}] Parsed evaluation results: {len(evidence)} plugins")
            app_logger.info(f"[Job {job_id}] Evaluation summary: {passed} PASS, {failed} FAIL, {unclear} UNCLEAR")
            app_logger.info(f"[Job {job_id}] Returning results dict to orchestrator")

            # Log failed plugins with reasoning
            for plugin_id, result in evidence.items():
                if result.get("status") == "FAIL":
                    plugin_info = next((p for p in plugins if str(p["id"]) == plugin_id), None)
                    plugin_name = plugin_info.get("name", plugin_id) if plugin_info else plugin_id
                    _log(
                        app_logger,
                        "warning",
                        f"[Job {job_id}] FAILED: {plugin_name} - {result.get('reasoning', 'No reasoning')[:150]}",
                    )

        # NOTE: Do NOT save the job here - let the orchestrator handle all job saves
        return evidence

    except Exception as e:
        if app_logger:
            app_logger.error(f"[Job {job_id}] Evaluation error: {e}", exc_info=True)
        return {}


def evaluate_reproducibility_plugins(job_id, llm_provider, app_logger=None, emit_event=None):
    """
    Evaluate reproducibility plugins using all available context.
    Runs after agent completes successfully.
    """
    stage3_start = time.time()

    try:
        if app_logger:
            app_logger.info(f"[{job_id}] === STAGE 3: Plugin Evaluation Starting ===")

        # Fetch all data using Peewee ORM
        paper_analysis_model = PaperAnalysisRepository.get(job_id)
        execution_details_model = ExecutionDetailsRepository.get(job_id)

        # Fetch artifacts
        artifacts_models = list(Artifact.select().where(Artifact.job == job_id))
        artifacts = [
            {"url": a.url, "artifact_type": a.artifact_type, "description": a.description} for a in artifacts_models
        ]

        if not paper_analysis_model or not execution_details_model:
            missing = []
            if not paper_analysis_model:
                missing.append("paper_analysis")
            if not execution_details_model:
                missing.append("execution_details")

            if app_logger:
                app_logger.warning(f"[{job_id}] Missing data for evaluation: {', '.join(missing)}")
            if emit_event:
                emit_event(job_id, {"step": "evaluation_skipped", "message": f"Skipped: Missing {', '.join(missing)}"})
            return False

        # Convert models to dicts for prompt building
        paper_analysis = {
            "pdf_hash": paper_analysis_model.pdf_hash,
            "title": paper_analysis_model.title,
            "abstract": paper_analysis_model.abstract,
            "extracted_text": paper_analysis_model.extracted_text,
            "methodology": paper_analysis_model.methodology,
            "dependencies": paper_analysis_model.dependencies,
            "dataset_description": paper_analysis_model.dataset_description,
            "claimed_results": paper_analysis_model.get_claimed_results()
            if hasattr(paper_analysis_model, "get_claimed_results")
            else json.loads(paper_analysis_model.claimed_results or "{}"),
        }

        execution_details = {
            "stdout_combined": execution_details_model.stdout_combined,
            "commands_run": execution_details_model.commands_run,
            "dependencies_used": execution_details_model.dependencies_used,
            "errors_summary": execution_details_model.errors_summary,
            "test_info": execution_details_model.test_info,
            "randomness_info": execution_details_model.randomness_info,
            "discovered_files": execution_details_model.get_discovered_files()
            if hasattr(execution_details_model, "get_discovered_files")
            else json.loads(execution_details_model.discovered_files or "[]"),
            "actual_results": execution_details_model.get_actual_results()
            if hasattr(execution_details_model, "get_actual_results")
            else json.loads(execution_details_model.actual_results or "{}"),
        }

        # Build evaluation prompt
        prompt = _build_evaluation_prompt(paper_analysis, execution_details, artifacts)

        # Check evaluation cache
        paper_hash = (
            paper_analysis.get("pdf_hash") or hashlib.md5(paper_analysis.get("extracted_text", "").encode()).hexdigest()
        )
        code_hash = hashlib.md5(execution_details.get("stdout_combined", "").encode()).hexdigest()

        # Check cache only if caching is enabled
        cached_evaluation = None
        if Config.ENABLE_CACHING:
            cached_evaluation = get_cached_evaluation(paper_hash, code_hash)

        if cached_evaluation:
            if app_logger:
                app_logger.info(f"[{job_id}] Cache hit for evaluation")
            if emit_event:
                emit_event(
                    job_id,
                    {
                        "step": "cache_hit_evaluation",
                        "message": "Using cached evaluation results",
                        # NOTE: Do NOT emit progress here - orchestrator controls all progress
                    },
                )
            evaluation_results = cached_evaluation
        else:
            if app_logger:
                app_logger.info(f"[{job_id}] Calling {llm_provider.get_name()} for plugin evaluation...")

            response_text = llm_provider.complete(messages=[{"role": "user", "content": prompt}], max_tokens=3000)

            # Parse response
            try:
                evaluation_results = json.loads(response_text)
            except json.JSONDecodeError:
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    evaluation_results = json.loads(json_str)
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                    evaluation_results = json.loads(json_str)
                else:
                    raise ValueError("Could not parse evaluation response")

            # Cache the results only if caching is enabled
            if Config.ENABLE_CACHING:
                store_evaluation_cache(paper_hash, code_hash, evaluation_results)

        # Store evaluation results using Peewee ORM
        for eval_item in evaluation_results.get("evaluations", []):
            PluginEvaluation.create(
                job_id=job_id,
                plugin_id=eval_item.get("plugin_id"),
                name=eval_item.get("name"),
                status=eval_item.get("status"),
                evidence=eval_item.get("evidence"),
                paper_supports=eval_item.get("paper_supports"),
                code_supports=eval_item.get("code_supports"),
                conclusion=eval_item.get("conclusion"),
            )

        # Update job report
        try:
            job = Job.get_by_id(job_id)
            if job:
                report = job.get_report()
                report["plugin_evaluations"] = evaluation_results.get("evaluations", [])
                job.set_report(report)
                job.save()
        except Exception:
            pass

        # Emit completion (without progress - orchestrator controls progress)
        stage3_duration = int((time.time() - stage3_start) * 1000)
        if emit_event:
            emit_event(
                job_id,
                {
                    "step": "evaluation_complete",
                    "message": f"Evaluated {len(evaluation_results.get('evaluations', []))} plugins",
                    "stage_duration_ms": stage3_duration,
                },
            )

        if app_logger:
            app_logger.info(f"[{job_id}] === PLUGIN EVALUATION COMPLETE in {stage3_duration}ms ===")

        return True

    except Exception as e:
        if app_logger:
            app_logger.error(f"[{job_id}] Error in plugin evaluation: {e}", exc_info=True)
        if emit_event:
            emit_event(job_id, {"step": "error", "message": f"Plugin evaluation failed: {str(e)}"})
        return False


def _build_evaluation_prompt(paper_analysis, execution_details, artifacts):
    """Build the evaluation prompt for Claude."""
    return f"""You are evaluating the reproducibility of a scientific paper and its code implementation.

PAPER CONTENT:
═══════════════════════════════════════════════════════════
Extracted Text (first 2000 chars):
{paper_analysis.get("extracted_text", "")[:2000]}

Methodology:
{paper_analysis.get("methodology", "No methodology found")}

Claimed Results:
{json.dumps(paper_analysis.get("claimed_results", {}), indent=2)}

Dependencies:
{paper_analysis.get("dependencies", "No dependencies mentioned")}

Dataset:
{paper_analysis.get("dataset_description", "No dataset description")}

CODE EXECUTION:
═══════════════════════════════════════════════════════════
Artifacts Found:
{json.dumps(artifacts, indent=2)}

Files in Repository:
{json.dumps(execution_details.get("discovered_files", [])[:20], default=str)}

Test Suite Information:
{execution_details.get("test_info", "No test info")}

Randomness Seed Information:
{execution_details.get("randomness_info", "No randomness info")}

Commands Run:
{execution_details.get("commands_run", "No commands recorded")[:1000]}

Execution Output (last 1500 chars):
{execution_details.get("stdout_combined", "No output recorded")[-1500:]}

Actual Results:
{json.dumps(execution_details.get("actual_results", {}), indent=2)}

Dependencies Used:
{execution_details.get("dependencies_used", "No dependencies logged")}

Errors Summary:
{execution_details.get("errors_summary", "No errors")}

EVALUATION TASKS:
═══════════════════════════════════════════════════════════

Evaluate 15 reproducibility aspects. For each, determine:
- status: "pass", "partial", or "fail"
- evidence: Quote or describe findings
- conclusion: Brief explanation

ASPECTS (Return JSON with evaluations array):

{{
  "evaluations": [
    {{"aspect_id": "dependencies_pinned", "name": "Dependencies Pinned", "status": "pass", "paper_supports": true, "code_supports": true, "evidence": "...", "conclusion": "..."}},
    ...15 total...
  ]
}}

Return ONLY valid JSON, no explanation."""
