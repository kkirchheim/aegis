"""Evaluation service - reproducibility evaluation and plugin checking."""

import json
import re
from typing import Dict, List, Optional

from models.database import Job, PaperAnalysis

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

REPOSITORY METADATA:
═══════════════════════════════════════════════════════════
Files in Repository:
{discovered_files}

Commands Run:
{commands_run}

Dependencies Used:
{dependencies_used}

Test Suite Information:
{test_info}

Randomness Seed Information:
{randomness_info}

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
    discovered_files: Optional[List[str]] = None,
    commands_run: Optional[str] = None,
    dependencies_used: Optional[str] = None,
    test_info: Optional[str] = None,
    randomness_info: Optional[str] = None,
) -> Optional[str]:
    """
    Merge all active plugins into single evaluation prompt.

    Args:
        plugins: List[{id, name, prompt_to_use}] - from PluginService.get_active_plugins_for_evaluation()
        paper_content: str - Content from paper analysis
        code_output: str - Output from code execution
        execution_log: str - Log from code execution
        discovered_files: Optional list of files found in the repository
        commands_run: Optional string of commands executed
        dependencies_used: Optional string of dependencies found
        test_info: Optional string of test suite information
        randomness_info: Optional string of randomness/seed information

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

    # Format discovered files list
    if discovered_files:
        files_text = ", ".join(discovered_files[:50])
        if len(discovered_files) > 50:
            files_text += f" ... and {len(discovered_files) - 50} more"
    else:
        files_text = "No file listing available"

    # Render full prompt with context (truncate to reasonable sizes)
    full_prompt = PLUGIN_EVAL_TEMPLATE.format(
        paper_content=paper_content[:20000] if paper_content else "",
        code_output=code_output[:30000] if code_output else "",
        execution_log=execution_log[:15000] if execution_log else "",
        discovered_files=files_text,
        commands_run=(commands_run or "No commands recorded")[:5000],
        dependencies_used=dependencies_used or "No dependencies logged",
        test_info=test_info or "No test info",
        randomness_info=randomness_info or "No randomness info",
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

            # Find plugin ID by name (try exact match, then prefix before ":")
            plugin_id = plugin_lookup.get(plugin_name)
            if not plugin_id and plugin_name and ":" in plugin_name:
                plugin_id = plugin_lookup.get(plugin_name.split(":")[0].strip())

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
    execution_details=None,
    temperature=0.0,
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
        execution_details: Optional ExecutionDetails model with structured metadata

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

        # Extract structured metadata from execution details if available
        discovered_files = None
        commands_run = None
        dependencies_used = None
        test_info = None
        randomness_info = None

        if execution_details:
            discovered_files = (
                execution_details.get_discovered_files() if hasattr(execution_details, "get_discovered_files") else None
            )
            commands_run = getattr(execution_details, "commands_run", None)
            dependencies_used = getattr(execution_details, "dependencies_used", None)
            test_info = getattr(execution_details, "test_info", None)
            randomness_info = getattr(execution_details, "randomness_info", None)

        # Render unified prompt
        prompt = render_evaluation_prompt(
            plugins,
            paper_content,
            code_output,
            execution_log,
            discovered_files=discovered_files,
            commands_run=commands_run,
            dependencies_used=dependencies_used,
            test_info=test_info,
            randomness_info=randomness_info,
        )

        if not prompt:
            if app_logger:
                app_logger.error(f"[Job {job_id}] Failed to render evaluation prompt")
            return {}

        # Single LLM call
        if app_logger:
            app_logger.info(f"[Job {job_id}] Calling LLM for evaluation ({len(plugins)} plugins)")

        response = llm_provider.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=3000, temperature=temperature
        )

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
