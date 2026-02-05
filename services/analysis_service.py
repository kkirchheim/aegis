"""Analysis service - PDF extraction, Claude parsing, artifact extraction."""

import json
from config import Config
from utils.pdf_utils import extract_pdf_text
from services.cache_service import get_cached_paper_analysis, store_paper_analysis_cache
from models.database import PaperAnalysis
from repositories import PaperAnalysisRepository


def extract_and_analyze_pdf(pdf_path, job_id, llm_provider, app_logger=None):
    """
    Extract PDF and analyze with Claude.
    
    Returns paper_info dict with artifacts and analysis results.
    """
    try:
        if app_logger:
            app_logger.info(f"[{job_id}] Extracting PDF text from {pdf_path}")
        
        # Extract PDF text
        pdf_text = extract_pdf_text(pdf_path, app_logger=app_logger)
        
        # Check cache first (only if caching is enabled)
        import hashlib
        pdf_hash = hashlib.md5(pdf_text.encode()).hexdigest()
        cached_paper_info = None
        if Config.ENABLE_CACHING:
            cached_paper_info = get_cached_paper_analysis(pdf_hash)
        
        if cached_paper_info:
            if app_logger:
                app_logger.info(f"[{job_id}] Cache hit for PDF analysis")
            paper_info = cached_paper_info
        else:
            if app_logger:
                app_logger.info(f"[{job_id}] Parsing paper with {llm_provider.get_name()}")
            
            paper_info = parse_paper_with_claude(pdf_text, llm_provider, app_logger)
            
            # Cache the results only if caching is enabled
            if Config.ENABLE_CACHING:
                store_paper_analysis_cache(pdf_hash, pdf_text, paper_info)
        
        # Store in job-specific table
        store_paper_analysis(job_id, paper_info, pdf_text)
        
        return pdf_text, paper_info
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"[{job_id}] Failed to analyze PDF: {str(e)}", exc_info=True)
        raise


def parse_paper_with_claude(pdf_text, llm_provider, app_logger=None):
    """
    Use Claude to extract code artifacts and reproducibility aspects from paper.
    
    Returns dict with artifacts, title, abstract, citations, etc.
    """
    if app_logger:
        app_logger.info(f"Parsing paper with {llm_provider.get_name()} (model: {llm_provider.get_model()}, input: {len(pdf_text)} chars)")
    
    prompt = f"""Analyze this scientific paper and extract:

1. **Title and Abstract**: Exact title and abstract from the paper
   
2. **Citations**: All references cited in the paper
   - Extract authors, year, title, and URL (if available)
   
3. **Code artifacts**: GitHub repos, datasets, supplementary code, Docker images
   - Include URLs, file links, or descriptions of where to find code
   
4. **Reproducibility aspects**:
   - Are hyperparameters documented?
   - Is dataset description sufficient?
   - Are implementation details provided?
   - Any known limitations or environment requirements?

Return valid JSON (no markdown, just JSON):
{{
  "title": "exact title of the paper",
  "abstract": "exact abstract text or first 300 chars if very long",
  "citations": [
    {{"authors": "Smith et al.", "year": 2020, "title": "Paper title here", "url": "https://doi.org/... or null"}},
    {{"authors": "Jones, Jane", "year": 2021, "title": "Another paper", "url": "https://..."}}
  ],
  "artifacts": [
    {{"url": "https://...", "type": "github_repo|dataset|supplementary|docker|other", "description": "..."}},
  ],
  "reproducibility_aspects": {{
    "hyperparameters_documented": true/false,
    "dataset_description": "brief summary or null",
    "implementation_details": "sufficient|partial|missing",
    "environment_requirements": "description or null",
    "notes": "any other relevant info"
  }},
  "summary": "brief analysis of reproducibility"
}}

Paper text:
{pdf_text[:20000]}
"""

    try:
        if app_logger:
            app_logger.info(f"Calling {llm_provider.get_name()} API with max_tokens=2000")
        
        response_text = llm_provider.complete(
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=2000
        )
        
        if app_logger:
            app_logger.info(f"Claude response received: {len(response_text)} chars")
        
        # Try to parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            if app_logger:
                app_logger.info(f"Direct JSON parsing failed, trying to extract from markdown")
            
            # If Claude wrapped in markdown, extract it
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                result = json.loads(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                result = json.loads(json_str)
            else:
                raise ValueError(f"Could not parse Claude response")
        
        return result
    
    except Exception as e:
        if app_logger:
            app_logger.error(f"Claude parsing failed: {str(e)}", exc_info=True)
        raise Exception(f"Claude parsing failed: {str(e)}")


def store_paper_analysis(job_id, paper_info, pdf_text):
    """Store paper analysis in database."""
    try:
        import hashlib
        pdf_hash = hashlib.md5(pdf_text.encode()).hexdigest()
        
        analysis = PaperAnalysis.create(
            job_id=job_id,
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
        analysis.save()
    except Exception as e:
        pass


def get_paper_analysis(job_id):
    """Get paper analysis for a job."""
    try:
        analysis = PaperAnalysisRepository.get(job_id)
        if analysis:
            return {
                "title": analysis.title,
                "abstract": analysis.abstract,
                "citations": analysis.get_citations(),
                "extracted_text": analysis.extracted_text,
                "methodology": analysis.methodology,
                "dependencies": analysis.dependencies,
                "dataset_description": analysis.dataset_description
            }
    except Exception as e:
        pass
    
    return None
