"""Pipeline orchestrator - orchestrates the 3-stage analysis pipeline."""

import sys
from typing import Callable, Optional
from services.analysis_service import extract_and_analyze_pdf
from services.docker_service import spawn_agent_container
from services.evaluation_service import evaluate_reproducibility_aspects
from services.job_service import update_job_status, store_artifacts
from services.event_dispatcher import EventDispatcher
from models.events import JobEvent


class PipelineOrchestrator:
    """Orchestrates the 3-stage analysis pipeline."""
    
    def __init__(
        self,
        analysis_service=None,
        docker_service=None,
        evaluation_service=None,
        job_service=None,
        dispatcher: EventDispatcher = None,
        logger: Callable = None,
    ):
        """
        Initialize orchestrator with dependencies.
        
        Args:
            analysis_service: Service for PDF analysis (uses extract_and_analyze_pdf)
            docker_service: Service for agent execution (uses spawn_agent_container)
            evaluation_service: Service for reproducibility evaluation (uses evaluate_reproducibility_aspects)
            job_service: Service for job updates (uses update_job_status, store_artifacts)
            dispatcher: Event dispatcher for emitting events
            logger: Logging function (defaults to stderr)
        """
        self.dispatcher = dispatcher
        self.logger = logger or self._default_logger
    
    @staticmethod
    def _default_logger(msg: str):
        """Default logger writes to stderr."""
        print(msg, file=sys.stderr)
    
    def emit_event(self, job_id: str, step: str, message: str = None, 
                   progress: float = None) -> None:
        """Emit event through dispatcher if available."""
        if self.dispatcher:
            event = JobEvent(
                job_id=job_id,
                step=step,
                message=message,
                progress=progress,
            )
            self.dispatcher.emit(event)
    
    def run_analysis(
        self,
        job_id: str,
        pdf_path: str,
        config,
        llm_provider,
    ) -> bool:
        """
        Run the complete 3-stage analysis pipeline.
        
        Stages:
        1. Extract and analyze PDF
        2. Execute code from artifacts
        3. Evaluate reproducibility
        
        Args:
            job_id: Job ID
            pdf_path: Path to PDF file
            config: Configuration object
            llm_provider: LLM provider for analysis
        
        Returns:
            True if analysis completed successfully, False otherwise
        """
        try:
            self.logger(f"[{job_id}] ===== ANALYSIS STARTED =====")
            self.emit_event(job_id, "starting", "Analysis starting...", progress=0)
            
            # Mark job as processing
            update_job_status(job_id, "processing")
            
            # Stage 1: Extract and analyze PDF
            if not self._run_stage_1(job_id, pdf_path, llm_provider):
                return False
            
            # Stage 2: Execute code
            if not self._run_stage_2(job_id, config):
                return False
            
            # Stage 3: Evaluate reproducibility
            if not self._run_stage_3(job_id, llm_provider):
                return False
            
            # Final completion
            self.logger(f"[{job_id}] >>> EMITTING FINAL COMPLETE EVENT")
            self.emit_event(job_id, "complete", "Analysis complete", progress=100)
            
            self.logger(f"[{job_id}] >>> MARKING JOB AS COMPLETED")
            update_job_status(job_id, "completed", progress=1.0, current_stage="completed")
            self.logger(f"[{job_id}] ===== ANALYSIS COMPLETE =====")
            
            return True
        
        except Exception as e:
            self.logger(f"[{job_id}] ERROR: {str(e)}")
            self.emit_event(job_id, "error", f"Error: {str(e)}", progress=100)
            update_job_status(job_id, "failed", error_message=str(e), progress=0.0, 
                            current_stage="failed")
            return False
    
    def _run_stage_1(self, job_id: str, pdf_path: str, llm_provider) -> bool:
        """
        Stage 1: Extract and analyze PDF.
        
        Returns True if successful, False otherwise.
        """
        try:
            self.logger(f"[{job_id}] >>> STAGE 1 STARTING")
            self.emit_event(job_id, "stage_1_starting", 
                          "Stage 1: Analyzing Paper...", progress=5)
            
            self.emit_event(job_id, "extracting_pdf", 
                          "Extracting text from PDF...")
            
            # Extract PDF
            pdf_text, paper_info = extract_and_analyze_pdf(pdf_path, job_id, llm_provider)
            
            self.emit_event(job_id, "pdf_extracted",
                          f"Extracted {len(pdf_text)} characters from PDF",
                          progress=40)
            
            # Store artifacts
            artifacts = paper_info.get("artifacts", [])
            store_artifacts(job_id, artifacts)
            
            self.logger(f"[{job_id}] >>> STAGE 1 COMPLETE")
            self.emit_event(job_id, "stage_1_complete",
                          f"Found {len(artifacts)} artifacts",
                          progress=40)
            
            # Store for next stage
            self._artifacts = artifacts
            return True
        
        except Exception as e:
            self.logger(f"[{job_id}] Stage 1 failed: {str(e)}")
            self.emit_event(job_id, "stage_1_error", f"Stage 1 failed: {str(e)}")
            return False
    
    def _run_stage_2(self, job_id: str, config) -> bool:
        """
        Stage 2: Execute code from artifacts.
        
        Returns True if successful (or no artifacts), False on error.
        """
        try:
            self.logger(f"[{job_id}] >>> STAGE 2 STARTING")
            self.emit_event(job_id, "stage_2_starting",
                          "Stage 2: Executing Code...",
                          progress=45)
            
            # Get GitHub artifacts from stage 1
            artifacts = getattr(self, '_artifacts', [])
            github_artifacts = [a for a in artifacts 
                              if a.get("type") == "github_repo" and a.get("url")]
            
            # Execute code from each artifact
            if github_artifacts:
                for i, artifact in enumerate(github_artifacts, 1):
                    repo_url = artifact.get("url")
                    self.emit_event(job_id, "running_agent",
                                  f"[{i}/{len(github_artifacts)}] Running agent on {repo_url}",
                                  progress=45 + int(30 * i / len(github_artifacts)))
                    
                    try:
                        spawn_agent_container(job_id, repo_url, config, 
                                            emit_event=lambda job_id, event_dict: 
                                                self.emit_event(job_id, **event_dict))
                    except Exception as e:
                        self.logger(f"[{job_id}] Agent failed for {repo_url}: {str(e)}")
                        self.emit_event(job_id, "agent_error",
                                      f"Agent failed for {repo_url}: {str(e)}")
            
            self.logger(f"[{job_id}] >>> STAGE 2 COMPLETE")
            self.emit_event(job_id, "stage_2_complete",
                          "Code execution complete",
                          progress=75)
            
            return True
        
        except Exception as e:
            self.logger(f"[{job_id}] Stage 2 failed: {str(e)}")
            self.emit_event(job_id, "stage_2_error", f"Stage 2 failed: {str(e)}")
            return False
    
    def _run_stage_3(self, job_id: str, llm_provider) -> bool:
        """
        Stage 3: Evaluate reproducibility.
        
        Returns True if successful, False otherwise.
        """
        try:
            self.logger(f"[{job_id}] >>> STAGE 3 STARTING")
            self.emit_event(job_id, "stage_3_starting",
                          "Stage 3: Evaluating Reproducibility...",
                          progress=80)
            
            # Run evaluation (synchronous - wait for completion)
            self.logger(f"[{job_id}] === Calling evaluate_reproducibility_aspects ===")
            evaluation_result = evaluate_reproducibility_aspects(
                job_id,
                llm_provider,
                emit_event=lambda job_id, event_dict: 
                    self.emit_event(job_id, **event_dict)
            )
            self.logger(f"[{job_id}] === evaluate_reproducibility_aspects returned: {evaluation_result} ===")
            
            if not evaluation_result:
                self.logger(f"[{job_id}] Evaluation failed")
                self.emit_event(job_id, "stage_3_error", "Evaluation failed")
                return False
            
            self.logger(f"[{job_id}] >>> STAGE 3 COMPLETE")
            self.emit_event(job_id, "stage_3_complete",
                          "Evaluation complete",
                          progress=100)
            
            return True
        
        except Exception as e:
            self.logger(f"[{job_id}] Stage 3 failed: {str(e)}")
            self.emit_event(job_id, "stage_3_error", f"Stage 3 failed: {str(e)}")
            return False


class PipelineOrchestratorFactory:
    """Factory for creating orchestrator instances."""
    
    @staticmethod
    def create(dispatcher: EventDispatcher = None):
        """Create a production orchestrator."""
        return PipelineOrchestrator(dispatcher=dispatcher)
    
    @staticmethod
    def create_test(dispatcher: EventDispatcher = None, mock_logger: Callable = None):
        """Create a test orchestrator with mocked dependencies."""
        logger = mock_logger or (lambda msg: None)  # Silent by default
        return PipelineOrchestrator(dispatcher=dispatcher, logger=logger)
