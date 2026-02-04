"""Cache service - paper analysis, code execution, and evaluation caching."""

import json
from config import Config
from models.database import CachePaperAnalysis, CacheCodeExecution, CacheEvaluation, ExecutionDetails, PaperAnalysis, AspectEvaluation, Job
from repositories import CachePaperAnalysisRepository, CacheCodeExecutionRepository, CacheEvaluationRepository


def get_cached_paper_analysis(pdf_hash):
    """
    Check if we've analyzed this PDF before (by hash).
    Returns paper_info dict if cached, None otherwise.
    """
    if not Config.ENABLE_CACHING:
        return None
    
    try:
        cache = CachePaperAnalysisRepository.get_by_hash(pdf_hash)
        if cache:
            return {
                "title": cache.title or "",
                "abstract": cache.abstract or "",
                "citations": json.loads(cache.citations or "[]"),
                "extracted_text": cache.extracted_text,
                "claimed_results": json.loads(cache.claimed_results or "{}"),
                "methodology": cache.methodology,
                "dependencies": cache.dependencies,
                "dataset_description": cache.dataset_description
            }
    except Exception as e:
        pass
    
    return None


def store_paper_analysis_cache(pdf_hash, pdf_text, paper_info):
    """Store paper analysis in cache for future reuse."""
    if not Config.ENABLE_CACHING:
        return
    
    try:
        # Try to get existing cache entry, otherwise create new one
        try:
            cache = CachePaperAnalysis.get(CachePaperAnalysis.pdf_hash == pdf_hash)
            # Update existing
            cache.title = paper_info.get("title", "")
            cache.abstract = paper_info.get("abstract", "")
            cache.citations = json.dumps(paper_info.get("citations", []))
            cache.extracted_text = pdf_text[:50000]
            cache.claimed_results = json.dumps(paper_info.get("claimed_results", {}))
            cache.methodology = paper_info.get("methodology", "")
            cache.dependencies = paper_info.get("dependencies", "")
            cache.dataset_description = paper_info.get("dataset_description", "")
            cache.save()
        except CachePaperAnalysis.DoesNotExist:
            # Create new
            cache = CachePaperAnalysis.create(
                pdf_hash=pdf_hash,
                title=paper_info.get("title", ""),
                abstract=paper_info.get("abstract", ""),
                citations=json.dumps(paper_info.get("citations", [])),
                extracted_text=pdf_text[:50000],
                claimed_results=json.dumps(paper_info.get("claimed_results", {})),
                methodology=paper_info.get("methodology", ""),
                dependencies=paper_info.get("dependencies", ""),
                dataset_description=paper_info.get("dataset_description", "")
            )
    except Exception as e:
        pass


def get_cached_evaluation(paper_hash, code_hash):
    """
    Check if we've evaluated this paper+code combination before.
    Returns evaluation dict if cached, None otherwise.
    """
    if not Config.ENABLE_CACHING:
        return None
    
    try:
        cache = CacheEvaluationRepository.get(paper_hash, code_hash)
        if cache:
            return json.loads(cache.evaluations)
    except Exception as e:
        pass
    
    return None


def store_evaluation_cache(paper_hash, code_hash, evaluations):
    """Store evaluation results in cache for future reuse."""
    if not Config.ENABLE_CACHING:
        return
    
    try:
        # Try to get existing cache entry, otherwise create new one
        try:
            cache = CacheEvaluation.get(
                (CacheEvaluation.paper_hash == paper_hash) &
                (CacheEvaluation.code_hash == code_hash)
            )
            # Update existing
            cache.evaluations = json.dumps(evaluations)
            cache.save()
        except CacheEvaluation.DoesNotExist:
            # Create new
            cache = CacheEvaluation.create(
                paper_hash=paper_hash,
                code_hash=code_hash,
                evaluations=json.dumps(evaluations)
            )
    except Exception as e:
        pass


def get_cache_stats():
    """Get cache statistics."""
    try:
        # Count jobs with cached execution results
        code_count = ExecutionDetails.select().where(ExecutionDetails.commands_run.is_null(False)).count()
        
        # Count jobs with cached paper analysis
        paper_count = PaperAnalysis.select().where(PaperAnalysis.extracted_text.is_null(False)).count()
        
        # Count distinct jobs with cached aspect evaluations
        eval_count = AspectEvaluation.select(AspectEvaluation.job).distinct().count()
        
        return {
            "paper_analysis": paper_count,
            "code_execution": code_count,
            "evaluation": eval_count,
            "total": paper_count + code_count + eval_count
        }
    except Exception as e:
        return {
            "paper_analysis": 0,
            "code_execution": 0,
            "evaluation": 0,
            "total": 0,
            "error": str(e)
        }


def clear_cache():
    """Clear all cached analysis data."""
    try:
        from pathlib import Path
        
        # Get all jobs with their PDF paths
        jobs = Job.select()
        deleted_count = 0
        
        # Delete PDF files
        for job in jobs:
            if job.pdf_path:
                pdf_file = Path(job.pdf_path)
                if pdf_file.exists():
                    pdf_file.unlink()
                    deleted_count += 1
        
        # Clear all job-related data (cascade should handle this, but be explicit)
        AspectEvaluation.delete().execute()
        ExecutionDetails.delete().execute()
        PaperAnalysis.delete().execute()
        
        # Clear cache data
        CacheEvaluation.delete().execute()
        CacheCodeExecution.delete().execute()
        CachePaperAnalysis.delete().execute()
        
        # Clear jobs (this should cascade to other tables)
        Job.delete().execute()
        
        return True, deleted_count
    except Exception as e:
        return False, 0
