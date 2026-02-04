"""Cache service - paper analysis, code execution, and evaluation caching."""

import json
from config import Config
from database import get_db


def get_cached_paper_analysis(pdf_hash):
    """
    Check if we've analyzed this PDF before (by hash).
    Returns paper_info dict if cached, None otherwise.
    """
    if not Config.ENABLE_CACHING:
        return None
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT title, abstract, citations, extracted_text, claimed_results, methodology, dependencies, dataset_description FROM cache_paper_analysis WHERE pdf_hash = ?",
            (pdf_hash,)
        )
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "title": row["title"] or "",
                "abstract": row["abstract"] or "",
                "citations": json.loads(row["citations"] or "[]"),
                "extracted_text": row["extracted_text"],
                "claimed_results": json.loads(row["claimed_results"]),
                "methodology": row["methodology"],
                "dependencies": row["dependencies"],
                "dataset_description": row["dataset_description"]
            }
    except Exception as e:
        pass
    
    return None


def store_paper_analysis_cache(pdf_hash, pdf_text, paper_info):
    """Store paper analysis in cache for future reuse."""
    if not Config.ENABLE_CACHING:
        return
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO cache_paper_analysis 
            (pdf_hash, title, abstract, citations, extracted_text, claimed_results, methodology, dependencies, dataset_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pdf_hash,
            paper_info.get("title", ""),
            paper_info.get("abstract", ""),
            json.dumps(paper_info.get("citations", [])),
            pdf_text[:50000],
            json.dumps(paper_info.get("claimed_results", {})),
            paper_info.get("methodology", ""),
            paper_info.get("dependencies", ""),
            paper_info.get("dataset_description", "")
        ))
        conn.commit()
        conn.close()
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
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT evaluations FROM cache_evaluation WHERE paper_hash = ? AND code_hash = ?",
            (paper_hash, code_hash)
        )
        row = c.fetchone()
        conn.close()
        
        if row:
            return json.loads(row["evaluations"])
    except Exception as e:
        pass
    
    return None


def store_evaluation_cache(paper_hash, code_hash, evaluations):
    """Store evaluation results in cache for future reuse."""
    if not Config.ENABLE_CACHING:
        return
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO cache_evaluation 
            (paper_hash, code_hash, evaluations)
            VALUES (?, ?, ?)
        """, (
            paper_hash,
            code_hash,
            json.dumps(evaluations)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        pass


def get_cache_stats():
    """Get cache statistics."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Count jobs with cached execution results
        c.execute("SELECT COUNT(*) as count FROM execution_details WHERE commands_run IS NOT NULL")
        code_row = c.fetchone()
        code_count = code_row["count"] if code_row else 0
        
        # Count jobs with cached paper analysis
        c.execute("SELECT COUNT(*) as count FROM paper_analysis WHERE extracted_text IS NOT NULL")
        paper_row = c.fetchone()
        paper_count = paper_row["count"] if paper_row else 0
        
        # Count jobs with cached aspect evaluations
        c.execute("SELECT COUNT(DISTINCT job_id) as count FROM aspect_evaluations")
        eval_row = c.fetchone()
        eval_count = eval_row["count"] if eval_row else 0
        
        conn.close()
        
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
        conn = get_db()
        c = conn.cursor()
        
        # Get all job IDs to delete associated files
        c.execute("SELECT id, pdf_path FROM jobs")
        jobs = c.fetchall()
        
        # Delete PDF files
        from pathlib import Path
        deleted_count = 0
        for job in jobs:
            if job["pdf_path"]:
                pdf_file = Path(job["pdf_path"])
                if pdf_file.exists():
                    pdf_file.unlink()
                    deleted_count += 1
        
        # Clear all job-related data
        c.execute("DELETE FROM aspect_evaluations")
        c.execute("DELETE FROM execution_details")
        c.execute("DELETE FROM paper_analysis")
        c.execute("DELETE FROM artifacts")
        c.execute("DELETE FROM events")
        c.execute("DELETE FROM jobs")
        
        # Clear all cache data
        c.execute("DELETE FROM cache_evaluation")
        c.execute("DELETE FROM cache_code_execution")
        c.execute("DELETE FROM cache_paper_analysis")
        
        conn.commit()
        conn.close()
        
        return True, deleted_count
    except Exception as e:
        return False, 0
