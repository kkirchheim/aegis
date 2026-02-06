"""Evaluation service - reproducibility evaluation and aspect checking."""

import json
import re
import time
import hashlib
from typing import List, Dict, Optional, Any
from config import Config
from models.database import PaperAnalysis, ExecutionDetails, Artifact, Job, AspectEvaluation
from repositories import PaperAnalysisRepository, ExecutionDetailsRepository, AspectEvaluationRepository, JobRepository
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

ASPECT_EVAL_TEMPLATE = """You are evaluating the reproducibility of a research paper across multiple dimensions.

For each aspect below, provide:
- Status: PASS / FAIL / UNCLEAR
- Reasoning: 1-2 sentences max

---

PAPER CONTENT:
{paper_content}

CODE EXECUTION OUTPUT:
{code_output}

EXECUTION LOG:
{execution_log}

---

ASPECTS TO EVALUATE:
{aspects_list}

---

RESULTS (format exactly as shown):"""

ASPECT_TEMPLATE = """
### {aspect_name}
{aspect_prompt}

---"""


# ============================================================================
# Phase 4: Unified Evaluation Pipeline Functions
# ============================================================================

def render_evaluation_prompt(
    aspects: List[Dict[str, str]],
    paper_content: str,
    code_output: str,
    execution_log: str,
) -> Optional[str]:
    """
    Merge all active aspects into single evaluation prompt.
    
    Args:
        aspects: List[{id, name, prompt_to_use}] - from AspectService.get_active_aspects_for_evaluation()
        paper_content: str - Content from paper analysis
        code_output: str - Output from code execution
        execution_log: str - Log from code execution
    
    Returns:
        str - Full prompt ready for LLM, or None if no aspects
    """
    if not aspects:
        return None
    
    # Build aspects section
    aspects_text = ""
    for aspect in aspects:
        prompt_to_use = aspect.get('prompt_to_use', aspect.get('prompt', ''))
        aspects_text += ASPECT_TEMPLATE.format(
            aspect_name=aspect['name'],
            aspect_prompt=prompt_to_use
        )
    
    # Render full prompt with context (truncate to reasonable sizes)
    full_prompt = ASPECT_EVAL_TEMPLATE.format(
        paper_content=paper_content[:20000] if paper_content else "",
        code_output=code_output[:10000] if code_output else "",
        execution_log=execution_log[:5000] if execution_log else "",
        aspects_list=aspects_text
    )
    
    return full_prompt


def parse_evaluation_response(
    response_text: str,
    aspects: List[Dict[str, str]],
    logger=None,
) -> Dict[str, Dict[str, str]]:
    """
    Parse LLM response into per-aspect results.
    
    Expected format:
    ### Aspect Name 1
    Status: PASS
    Reasoning: ...
    
    ### Aspect Name 2
    Status: FAIL
    Reasoning: ...
    
    Args:
        response_text: str - Response from LLM
        aspects: List[{id, name, ...}] - Same aspects that were evaluated
        logger: Optional logger (function or logger object)
    
    Returns:
        dict: {aspect_id: {status, reasoning}} or empty dict if parsing fails
    """
    results = {}
    
    for aspect in aspects:
        aspect_id = str(aspect['id'])
        aspect_name = aspect['name']
        
        # Find section for this aspect: ### AspectName ... next ### or end
        pattern = rf"### {re.escape(aspect_name)}.*?(?=### |\Z)"
        match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            # Aspect not found in response
            results[aspect_id] = {
                "status": "UNCLEAR",
                "reasoning": "Response did not include evaluation for this aspect"
            }
            if logger:
                _log(logger, "warning", f"[PARSE] {aspect_name}: NOT FOUND in response")
            continue
        
        section = match.group(0)
        
        # Extract status (PASS / FAIL / UNCLEAR)
        status_match = re.search(r"\b(PASS|FAIL|UNCLEAR)\b", section, re.IGNORECASE)
        status = status_match.group(1).upper() if status_match else "UNCLEAR"
        
        # Extract reasoning (everything after "Reasoning:" or after status line)
        reasoning_match = re.search(
            r"(?:Reasoning|reasoning):\s*(.+?)(?=###|\Z)",
            section,
            re.DOTALL
        )
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()[:500]  # Max 500 chars
        else:
            # Fallback: take last 2 lines
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            reasoning = ' '.join(lines[-2:])[:500]
        
        results[aspect_id] = {
            "status": status,
            "reasoning": reasoning
        }
        
        # Log each aspect result
        if logger:
            if status == "PASS":
                _log(logger, "info", f"[PARSE] {aspect_name}: PASS")
            elif status == "FAIL":
                _log(logger, "warning", f"[PARSE] {aspect_name}: FAIL - {reasoning[:100]}")
            else:
                _log(logger, "info", f"[PARSE] {aspect_name}: {status}")
    
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
    Single LLM call to evaluate all active aspects (Phase 4).
    
    Args:
        job_id: str - Job ID
        paper_analysis: PaperAnalysis - Paper analysis result
        code_output: str - Code execution output
        execution_log: str - Code execution log
        llm_provider: LLM provider instance
        app_logger: Optional logger
    
    Returns:
        dict: evaluation_results {aspect_id: {status, reasoning}}
    """
    from services.aspect_service import AspectService
    
    try:
        job = Job.get_by_id(job_id)
        
        # Get active aspects for this user
        aspects = AspectService.get_active_aspects_for_evaluation(job.user.id)
        
        if not aspects:
            # No active aspects - skip evaluation
            if app_logger:
                app_logger.warning(f"[Job {job_id}] No active aspects for user {job.user.id}, skipping evaluation")
            job.status = "completed"
            job.set_evaluation_results({})
            job.save()
            return {}
        
        # Get paper content
        paper_content = paper_analysis.extracted_text or ""
        
        # Render unified prompt
        prompt = render_evaluation_prompt(aspects, paper_content, code_output, execution_log)
        
        if not prompt:
            if app_logger:
                app_logger.error(f"[Job {job_id}] Failed to render evaluation prompt")
            job.status = "error"
            job.save()
            return {}
        
        # Single LLM call
        if app_logger:
            app_logger.info(f"[Job {job_id}] Calling LLM for evaluation ({len(aspects)} aspects)")
        
        response = llm_provider.complete(
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=3000
        )
        
        # Parse response with detailed logging
        evaluation_results = parse_evaluation_response(response, aspects, logger=app_logger)
        
        # Store results
        job.set_evaluation_results(evaluation_results)
        job.status = "completed"
        job.save()
        
        # Log summary with per-aspect details
        passed = sum(1 for r in evaluation_results.values() if r.get('status') == 'PASS')
        failed = sum(1 for r in evaluation_results.values() if r.get('status') == 'FAIL')
        unclear = sum(1 for r in evaluation_results.values() if r.get('status') == 'UNCLEAR')
        if app_logger:
            app_logger.info(f"[Job {job_id}] Evaluation complete: {passed} PASS, {failed} FAIL, {unclear} UNCLEAR")
            
            # Log failed aspects with reasoning
            for aspect_id, result in evaluation_results.items():
                if result.get('status') == 'FAIL':
                    aspect_info = next((a for a in aspects if str(a['id']) == aspect_id), None)
                    aspect_name = aspect_info.get('name', aspect_id) if aspect_info else aspect_id
                    _log(app_logger, "warning", f"[Job {job_id}] FAILED: {aspect_name} - {result.get('reasoning', 'No reasoning')[:150]}")
        
        return evaluation_results
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"[Job {job_id}] Evaluation error: {e}", exc_info=True)
        try:
            job = Job.get_by_id(job_id)
            job.status = "error"
            job.save()
        except:
            pass
        return {}


def evaluate_reproducibility_aspects(job_id, llm_provider, app_logger=None, emit_event=None):
    """
    Evaluate reproducibility aspects using all available context.
    Runs after agent completes successfully.
    """
    stage3_start = time.time()
    
    try:
        if app_logger:
            app_logger.info(f"[{job_id}] === STAGE 3: Aspect Evaluation Starting ===")
        
        # Fetch all data using Peewee ORM
        paper_analysis_model = PaperAnalysisRepository.get(job_id)
        execution_details_model = ExecutionDetailsRepository.get(job_id)
        
        # Fetch artifacts
        artifacts_models = list(Artifact.select().where(Artifact.job == job_id))
        artifacts = [
            {
                "url": a.url,
                "artifact_type": a.artifact_type,
                "description": a.description
            }
            for a in artifacts_models
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
                emit_event(job_id, {
                    "step": "evaluation_skipped",
                    "message": f"Skipped: Missing {', '.join(missing)}"
                })
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
            "claimed_results": paper_analysis_model.get_claimed_results() if hasattr(paper_analysis_model, 'get_claimed_results') else json.loads(paper_analysis_model.claimed_results or "{}")
        }
        
        execution_details = {
            "stdout_combined": execution_details_model.stdout_combined,
            "commands_run": execution_details_model.commands_run,
            "dependencies_used": execution_details_model.dependencies_used,
            "errors_summary": execution_details_model.errors_summary,
            "test_info": execution_details_model.test_info,
            "randomness_info": execution_details_model.randomness_info,
            "discovered_files": execution_details_model.get_discovered_files() if hasattr(execution_details_model, 'get_discovered_files') else json.loads(execution_details_model.discovered_files or "[]"),
            "actual_results": execution_details_model.get_actual_results() if hasattr(execution_details_model, 'get_actual_results') else json.loads(execution_details_model.actual_results or "{}")
        }
        
        # Build evaluation prompt
        prompt = _build_evaluation_prompt(paper_analysis, execution_details, artifacts)
        
        # Check evaluation cache
        paper_hash = paper_analysis.get("pdf_hash") or hashlib.md5(paper_analysis.get("extracted_text", "").encode()).hexdigest()
        code_hash = hashlib.md5(execution_details.get("stdout_combined", "").encode()).hexdigest()
        
        # Check cache only if caching is enabled
        cached_evaluation = None
        if Config.ENABLE_CACHING:
            cached_evaluation = get_cached_evaluation(paper_hash, code_hash)
        
        if cached_evaluation:
            if app_logger:
                app_logger.info(f"[{job_id}] Cache hit for evaluation")
            if emit_event:
                emit_event(job_id, {
                    "step": "cache_hit_evaluation",
                    "message": "Using cached evaluation results"
                    # NOTE: Do NOT emit progress here - orchestrator controls all progress
                })
            evaluation_results = cached_evaluation
        else:
            if app_logger:
                app_logger.info(f"[{job_id}] Calling {llm_provider.get_name()} for aspect evaluation...")
            
            response_text = llm_provider.complete(
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=3000
            )
            
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
            AspectEvaluation.create(
                job_id=job_id,
                aspect_id=eval_item.get("aspect_id"),
                name=eval_item.get("name"),
                status=eval_item.get("status"),
                evidence=eval_item.get("evidence"),
                paper_supports=eval_item.get("paper_supports"),
                code_supports=eval_item.get("code_supports"),
                conclusion=eval_item.get("conclusion")
            )
        
        # Update job report
        try:
            job = Job.get_by_id(job_id)
            if job:
                report = job.get_report()
                report["aspect_evaluations"] = evaluation_results.get("evaluations", [])
                job.set_report(report)
                job.save()
        except:
            pass
        
        # Emit completion (without progress - orchestrator controls progress)
        stage3_duration = int((time.time() - stage3_start) * 1000)
        if emit_event:
            emit_event(job_id, {
                "step": "evaluation_complete",
                "message": f"Evaluated {len(evaluation_results.get('evaluations', []))} aspects",
                "stage_duration_ms": stage3_duration
            })
        
        if app_logger:
            app_logger.info(f"[{job_id}] === ASPECT EVALUATION COMPLETE in {stage3_duration}ms ===")
        
        return True
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"[{job_id}] Error in aspect evaluation: {e}", exc_info=True)
        if emit_event:
            emit_event(job_id, {
                "step": "error",
                "message": f"Aspect evaluation failed: {str(e)}"
            })
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
