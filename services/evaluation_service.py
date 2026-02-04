"""Evaluation service - reproducibility evaluation and aspect checking."""

import json
import time
import hashlib
from database import get_db
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
        
        # Fetch all data
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT * FROM paper_analysis WHERE job_id = ?", (job_id,))
        paper_analysis_row = c.fetchone()
        
        c.execute("SELECT * FROM execution_details WHERE job_id = ?", (job_id,))
        execution_details_row = c.fetchone()
        
        c.execute("SELECT url, artifact_type, description FROM artifacts WHERE job_id = ?", (job_id,))
        artifacts = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        if not paper_analysis_row or not execution_details_row:
            if app_logger:
                app_logger.warning(f"[{job_id}] Missing data for evaluation")
            if emit_event:
                emit_event(job_id, {
                    "step": "evaluation_skipped",
                    "message": "Skipped: Missing required data for evaluation"
                })
            return False
        
        # Convert rows to dicts
        paper_analysis = dict(paper_analysis_row)
        execution_details = dict(execution_details_row)
        
        # Parse JSON fields
        paper_analysis["claimed_results"] = json.loads(paper_analysis.get("claimed_results", "{}"))
        execution_details["actual_results"] = json.loads(execution_details.get("actual_results", "{}"))
        
        try:
            discovered_files_json = execution_details.get("discovered_files", "[]")
            execution_details["discovered_files"] = json.loads(discovered_files_json) if isinstance(discovered_files_json, str) else (discovered_files_json or [])
        except:
            execution_details["discovered_files"] = []
        
        # Build evaluation prompt
        prompt = _build_evaluation_prompt(paper_analysis, execution_details, artifacts)
        
        # Check evaluation cache
        paper_hash = paper_analysis.get("pdf_hash") or hashlib.md5(paper_analysis.get("extracted_text", "").encode()).hexdigest()
        code_hash = hashlib.md5(execution_details.get("stdout_combined", "").encode()).hexdigest()
        
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
            
            # Cache the results
            store_evaluation_cache(paper_hash, code_hash, evaluation_results)
        
        # Store evaluation results
        conn = get_db()
        c = conn.cursor()
        
        for eval_item in evaluation_results.get("evaluations", []):
            c.execute("""
                INSERT INTO aspect_evaluations
                (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                eval_item.get("aspect_id"),
                eval_item.get("name"),
                eval_item.get("status"),
                eval_item.get("evidence"),
                eval_item.get("paper_supports"),
                eval_item.get("code_supports"),
                eval_item.get("conclusion")
            ))
        
        conn.commit()
        conn.close()
        
        # Update job report
        job_conn = get_db()
        job_c = job_conn.cursor()
        job_c.execute("SELECT report FROM jobs WHERE id = ?", (job_id,))
        job_row = job_c.fetchone()
        job_conn.close()
        
        if job_row:
            report = json.loads(job_row["report"]) if job_row["report"] else {}
            report["aspect_evaluations"] = evaluation_results.get("evaluations", [])
            
            job_conn = get_db()
            job_c = job_conn.cursor()
            job_c.execute(
                "UPDATE jobs SET report = ? WHERE id = ?",
                (json.dumps(report), job_id)
            )
            job_conn.commit()
            job_conn.close()
        
        # Emit completion
        stage3_duration = int((time.time() - stage3_start) * 1000)
        if emit_event:
            emit_event(job_id, {
                "step": "stage_3_complete",
                "message": f"Evaluated {len(evaluation_results.get('evaluations', []))} aspects",
                "progress": 100,
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
