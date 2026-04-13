"""Pipeline orchestrator - orchestrates the 3-stage analysis pipeline."""

import json
import sys
from datetime import datetime
from typing import Callable
from urllib.parse import urlparse

from models.events import JobEvent
from services.analysis_service import extract_and_analyze_pdf
from services.docker_service import spawn_agent_container
from services.event_dispatcher import EventDispatcher
from services.job_service import store_artifacts, update_job_status


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

    def emit_event(
        self, job_id: str, step: str, message: str = None, progress: float = None, stage_duration_ms: int = None
    ) -> None:
        """Emit event through dispatcher if available."""
        if self.dispatcher:
            event = JobEvent(
                job_id=job_id,
                step=step,
                message=message,
                progress=progress,
                stage_duration_ms=stage_duration_ms,
            )
            self.dispatcher.emit(event)

    def run_analysis(
        self,
        job_id: str,
        pdf_path: str,
        config,
        llm_provider,
        manual_artifacts=None,
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
            self.emit_event(job_id, "starting", "Analysis starting...", progress=0.0)

            # Mark job as processing
            update_job_status(job_id, "processing", progress=0.0)

            # Stage 1: Extract and analyze PDF
            if not self._run_stage_1(job_id, pdf_path, llm_provider, manual_artifacts=manual_artifacts or []):
                update_job_status(
                    job_id,
                    "failed",
                    error_message="Stage 1 (paper analysis) failed",
                    progress=0.0,
                    current_stage="failed",
                )
                return False

            # Stage 2: Execute code
            if not self._run_stage_2(job_id, config):
                update_job_status(
                    job_id,
                    "failed",
                    error_message="Stage 2 (code execution) failed",
                    progress=0.33,
                    current_stage="failed",
                )
                return False

            # Stage 3: Evaluate reproducibility
            if not self._run_stage_3(job_id, llm_provider):
                update_job_status(
                    job_id, "failed", error_message="Stage 3 (evaluation) failed", progress=0.66, current_stage="failed"
                )
                return False

            # Final completion - only update job status (don't emit progress event)
            self.logger(f"[{job_id}] >>> MARKING JOB AS COMPLETED")
            update_job_status(job_id, "completed", progress=1.0, current_stage="completed")
            self.emit_event(job_id, "complete", "Analysis complete")
            self.logger(f"[{job_id}] ===== ANALYSIS COMPLETE =====")

            return True

        except Exception as e:
            self.logger(f"[{job_id}] ERROR: {str(e)}")
            # On error: update status first, then emit event (no progress in event)
            update_job_status(job_id, "failed", error_message=str(e), progress=0.0, current_stage="failed")
            self.emit_event(job_id, "error", f"Error: {str(e)}")
            return False

    @staticmethod
    def _normalize_artifact(artifact):
        """Normalize artifact payloads to the internal shape."""
        if not artifact or not artifact.get("url"):
            return None

        url = artifact.get("url", "").strip().rstrip("/")
        if not url:
            return None

        artifact_type = artifact.get("type") or artifact.get("artifact_type")
        if not artifact_type:
            parsed = urlparse(url)
            hostname = (parsed.netloc or "").lower()
            artifact_type = "github_repo" if "github.com" in hostname else "other"

        normalized = {
            "url": url,
            "type": artifact_type,
        }
        if artifact.get("description"):
            normalized["description"] = artifact.get("description")

        return normalized

    @classmethod
    def _merge_artifacts(cls, extracted_artifacts, manual_artifacts):
        """Merge extracted and manual artifacts, preferring richer metadata."""
        merged = {}

        for artifact in extracted_artifacts or []:
            normalized = cls._normalize_artifact(artifact)
            if normalized:
                merged[normalized["url"]] = normalized

        for artifact in manual_artifacts or []:
            normalized = cls._normalize_artifact(artifact)
            if not normalized:
                continue

            existing = merged.get(normalized["url"])
            if existing:
                if not existing.get("description") and normalized.get("description"):
                    existing["description"] = normalized["description"]
                if existing.get("type") in (None, "", "other") and normalized.get("type"):
                    existing["type"] = normalized["type"]
                continue

            merged[normalized["url"]] = normalized

        return list(merged.values())

    def _run_stage_1(self, job_id: str, pdf_path: str, llm_provider, manual_artifacts=None) -> bool:
        """
        Stage 1: Extract and analyze PDF.

        Progress: 0.0 -> 0.33

        Returns True if successful, False otherwise.
        """
        try:
            self.logger(f"[{job_id}] >>> STAGE 1 STARTING")
            self.emit_event(job_id, "stage_1_starting", "Stage 1: Analyzing Paper...", progress=0.05)

            self.emit_event(job_id, "extracting_pdf", "Extracting text from PDF...")

            # Extract PDF
            pdf_text, paper_info = extract_and_analyze_pdf(pdf_path, job_id, llm_provider)

            self.emit_event(job_id, "pdf_extracted", f"Extracted {len(pdf_text)} characters from PDF", progress=0.25)

            # Store artifacts
            artifacts = self._merge_artifacts(paper_info.get("artifacts", []), manual_artifacts or [])
            store_artifacts(job_id, artifacts)

            self.logger(f"[{job_id}] >>> STAGE 1 COMPLETE")
            self.emit_event(job_id, "stage_1_complete", f"Found {len(artifacts)} artifacts", progress=0.33)

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

        Progress: 0.33 -> 0.66

        Returns True if successful (or no artifacts), False on error.
        """
        try:
            self.logger(f"[{job_id}] >>> STAGE 2 STARTING")
            self.emit_event(job_id, "stage_2_starting", "Stage 2: Executing Code...", progress=0.35)

            # Get GitHub artifacts from stage 1
            artifacts = getattr(self, "_artifacts", [])
            github_artifacts = [a for a in artifacts if a.get("type") == "github_repo" and a.get("url")]

            # Execute code from each artifact
            if github_artifacts:
                for i, artifact in enumerate(github_artifacts, 1):
                    repo_url = artifact.get("url")
                    # Progress from 0.35 to 0.66 as we process artifacts
                    progress = 0.35 + (0.31 * i / len(github_artifacts))
                    self.emit_event(
                        job_id,
                        "running_agent",
                        f"[{i}/{len(github_artifacts)}] Running agent on {repo_url}",
                        progress=progress,
                    )

                    try:
                        spawn_agent_container(
                            job_id,
                            repo_url,
                            config,
                            emit_event=lambda job_id, event_dict: self.emit_event(job_id, **event_dict),
                        )
                    except Exception as e:
                        self.logger(f"[{job_id}] Agent failed for {repo_url}: {str(e)}")
                        self.emit_event(job_id, "agent_error", f"Agent failed for {repo_url}: {str(e)}")

            self.logger(f"[{job_id}] >>> STAGE 2 COMPLETE")
            self.emit_event(job_id, "stage_2_complete", "Code execution complete", progress=0.66)

            return True

        except Exception as e:
            self.logger(f"[{job_id}] Stage 2 failed: {str(e)}")
            self.emit_event(job_id, "stage_2_error", f"Stage 2 failed: {str(e)}")
            return False

    def _run_stage_3(self, job_id: str, llm_provider) -> bool:
        """
        Stage 3: Evaluate reproducibility across all active plugins.

        Single LLM call evaluates all active plugins in one pass.
        Stores per-plugin results in job.evidence.

        Progress: 0.66 -> 1.0

        Returns True if successful, False otherwise.
        """
        import json
        import time

        from models.database import ExecutionDetails, Job, PaperAnalysis
        from services.evaluation_service import evaluate_paper
        from services.plugin_service import PluginService

        # Wrap logger to handle both function and object types (like stage_3_evaluation does)
        class LoggerWrapper:
            def __init__(self, original_logger):
                self.original = original_logger

            def __call__(self, msg):
                if self.original and callable(self.original):
                    self.original(msg)

            def info(self, msg):
                if self.original and callable(self.original):
                    self.original(f"[INFO] {msg}")

            def warning(self, msg):
                if self.original and callable(self.original):
                    self.original(f"[WARNING] {msg}")

            def error(self, msg, exc_info=False):
                if self.original and callable(self.original):
                    self.original(f"[ERROR] {msg}")

            def debug(self, msg):
                if self.original and callable(self.original):
                    self.original(f"[DEBUG] {msg}")

        wrapped_logger = LoggerWrapper(self.logger)

        try:
            wrapped_logger(f"[{job_id}] >>> STAGE 3 STARTING")

            job = Job.get_by_id(job_id)

            # Get active plugins for this user
            active_plugins = PluginService.get_active_plugins_for_evaluation(job.user_id)
            wrapped_logger(f"[{job_id}] Stage 3: {len(active_plugins)} active plugins for evaluation")

            # Emit progress event: evaluation starting
            self.emit_event(
                job_id, "stage_3_starting", f"Stage 3: Evaluating across {len(active_plugins)} plugins", progress=0.75
            )

            # If no active plugins, skip evaluation (complete with empty results)
            if not active_plugins:
                wrapped_logger(f"[{job_id}] No active plugins, skipping evaluation")
                job.evidence = "{}"
                job.status = "completed"
                job.current_stage = "evaluation"
                job.progress = 1.0
                job.save()

                self.emit_event(job_id, "stage_3_complete", "Evaluation skipped (no active plugins)", progress=1.0)
                return True

            # Get paper analysis and execution details
            paper_analysis = None
            execution = None

            try:
                paper_analysis = PaperAnalysis.get(PaperAnalysis.job == job_id)
                execution = ExecutionDetails.get(ExecutionDetails.job == job_id)
            except Exception:
                pass

            if not paper_analysis or not execution:
                raise Exception("Missing paper analysis or execution details")

            # Evaluate paper across all active plugins
            start_time = time.time()

            evidence = evaluate_paper(
                job_id=job_id,
                paper_analysis=paper_analysis,
                code_output=execution.stdout_combined or "",
                execution_log=execution.errors_summary or "",
                llm_provider=llm_provider,
                app_logger=wrapped_logger,  # Pass wrapped logger, not raw function
                execution_details=execution,
            )

            int((time.time() - start_time) * 1000)

            # Count results
            len(evidence)
            passed = sum(1 for r in evidence.values() if r.get("status") == "PASS")
            failed = sum(1 for r in evidence.values() if r.get("status") == "FAIL")
            unclear = sum(1 for r in evidence.values() if r.get("status") == "UNCLEAR")

            self.logger(f"[{job_id}] Evaluation complete: {passed} PASS, {failed} FAIL, {unclear} UNCLEAR")

            # Update job with results
            job.evidence = json.dumps(evidence)
            job.status = "completed"
            job.current_stage = "evaluation"
            job.progress = 1.0
            job.completed_at = datetime.now()

            # Log before saving (for debugging)
            self.logger(f"[{job_id}] Saving {len(evidence)} evidence results to database")
            self.logger(f"[{job_id}] evidence JSON length: {len(job.evidence)} chars")

            job.save()

            # Verify it was saved
            self.logger(f"[{job_id}] Job saved successfully. Fetching to verify...")
            verify_job = Job.get_by_id(job_id)
            verify_results = verify_job.get_evidence()
            self.logger(f"[{job_id}] Verified {len(verify_results)} plugins in database")

            # Emit completion event
            self.emit_event(
                job_id, "stage_3_complete", f"Evaluation complete: {passed} passed, {failed} failed", progress=1.0
            )

            self.logger(f"[{job_id}] >>> STAGE 3 COMPLETE")

            return True

        except Exception as e:
            self.logger(f"[{job_id}] Stage 3 failed: {str(e)}")

            try:
                job = Job.get_by_id(job_id)
                job.status = "error"
                job.error_message = f"Evaluation failed: {str(e)}"
                job.current_stage = "evaluation"
                job.save()
            except Exception:
                pass

            self.emit_event(job_id, "stage_3_error", f"Stage 3 failed: {str(e)}")
            return False


# ============================================================================
# Phase 5: Standalone stage_3_evaluation function for testing
# ============================================================================


def stage_3_evaluation(job_id, app_logger=None):
    """
    Stage 3: Evaluate paper across all active reproducibility plugins.

    Single LLM call evaluates all active plugins in one pass.
    Stores per-plugin results in job.evidence.

    Args:
        job_id: Job ID
        app_logger: Optional logger (function or logger object)

    Returns:
        bool: True if successful, False otherwise
    """

    from models.database import ExecutionDetails, Job, PaperAnalysis
    from services.evaluation_service import evaluate_paper
    from services.event_dispatcher import EventDispatcher, JobEvent
    from services.plugin_service import PluginService

    def _emit(job_id, step, message=None, progress=None, stage_duration_ms=None):
        """Helper to emit events, silently ignoring failures."""
        try:
            EventDispatcher().emit(
                JobEvent(
                    job_id=job_id, step=step, message=message, progress=progress, stage_duration_ms=stage_duration_ms
                )
            )
        except Exception:
            pass

    # Create a wrapper logger that handles both function and logger objects
    class LoggerWrapper:
        def __init__(self, original_logger):
            self.original = original_logger

        def info(self, msg):
            if self.original is None:
                return  # Silent
            if callable(self.original):
                self.original(f"[INFO] {msg}")
            elif hasattr(self.original, "info"):
                self.original.info(msg)

        def warning(self, msg):
            if self.original is None:
                return  # Silent
            if callable(self.original):
                self.original(f"[WARNING] {msg}")
            elif hasattr(self.original, "warning"):
                self.original.warning(msg)

        def error(self, msg, exc_info=False):
            if self.original is None:
                print(f"[ERROR] {msg}", flush=True)  # At least print to stdout/stderr
                return
            if callable(self.original):
                self.original(f"[ERROR] {msg}")
            elif hasattr(self.original, "error"):
                self.original.error(msg, exc_info=exc_info)

        def debug(self, msg):
            if self.original is None:
                return  # Silent
            if callable(self.original):
                self.original(f"[DEBUG] {msg}")
            elif hasattr(self.original, "debug"):
                self.original.debug(msg)

    # Create logger wrapper
    if app_logger is None:
        # Create silent logger
        logger = LoggerWrapper(None)
    else:
        logger = LoggerWrapper(app_logger)

    job = None
    try:
        job = Job.get_by_id(job_id)
    except Exception as e:
        logger.error(f"[Job {job_id}] ERROR: Job not found - {e}", exc_info=True)
        return False

    try:
        # Get active plugins for this user
        active_plugins = PluginService.get_active_plugins_for_evaluation(job.user_id)
        logger.info(f"[Job {job_id}] Stage 3: {len(active_plugins)} active plugins for evaluation")

        # Emit progress event: evaluation starting
        _emit(job_id, "stage_3_start", f"Evaluating across {len(active_plugins)} plugins", progress=0.66)

        # If no active plugins, skip evaluation (complete with empty results)
        if not active_plugins:
            logger.warning(f"[Job {job_id}] No active plugins, skipping evaluation")
            job.evidence = "{}"
            job.status = "completed"
            job.current_stage = "evaluation"
            job.progress = 1.0
            job.save()

            _emit(job_id, "stage_3_complete", "Evaluation skipped (no active plugins)", progress=1.0)
            return True

        # Get paper analysis and execution details
        paper_analysis = None
        execution = None

        try:
            paper_analysis = PaperAnalysis.get(PaperAnalysis.job == job_id)
            execution = ExecutionDetails.get(ExecutionDetails.job == job_id)
        except Exception:
            pass

        if not paper_analysis or not execution:
            raise Exception("Missing paper analysis or execution details")

        # Evaluate paper across all active plugins
        import time

        start_time = time.time()

        evidence = evaluate_paper(
            job_id=job_id,
            paper_analysis=paper_analysis,
            code_output=execution.stdout_combined or "",
            execution_log=execution.errors_summary or "",
            llm_provider=None,  # Will use default from config
            app_logger=logger,  # Pass wrapped logger that handles both function and object
            execution_details=execution,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Count results
        len(evidence)
        passed = sum(1 for r in evidence.values() if r.get("status") == "PASS")
        failed = sum(1 for r in evidence.values() if r.get("status") == "FAIL")
        unclear = sum(1 for r in evidence.values() if r.get("status") == "UNCLEAR")

        logger.info(f"[Job {job_id}] Evaluation complete: {passed} PASS, {failed} FAIL, {unclear} UNCLEAR")

        # Update job with results
        job.evidence = json.dumps(evidence)
        job.status = "completed"
        job.current_stage = "evaluation"
        job.progress = 1.0
        job.completed_at = datetime.now()
        job.save()

        # Emit completion event
        _emit(
            job_id,
            "stage_3_complete",
            f"Evaluation complete: {passed} passed, {failed} failed",
            progress=1.0,
            stage_duration_ms=elapsed_ms,
        )

        return True

    except Exception as e:
        import traceback

        logger.error(f"[Job {job_id}] Stage 3 evaluation failed: {e}", exc_info=True)
        logger.error(f"[Job {job_id}] Traceback: {traceback.format_exc()}")

        if job:
            job.status = "error"
            job.error_message = f"Evaluation failed: {str(e)}\n{traceback.format_exc()}"
            job.current_stage = "evaluation"
            job.save()

        _emit(job_id, "stage_3_error", f"Evaluation error: {str(e)}", progress=1.0)

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
