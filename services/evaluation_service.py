"""Evaluation service - reproducibility evaluation and aspect checking."""

import json
import time
import hashlib
from config import Config
from models.database import PaperAnalysis, ExecutionDetails, Artifact, Job, AspectEvaluation
from repositories import PaperAnalysisRepository, ExecutionDetailsRepository, AspectEvaluationRepository, JobRepository
from services.cache_service import get_cached_evaluation, store_evaluation_cache


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
                    "message": "Using cached evaluation results",
                    "progress": 85
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
