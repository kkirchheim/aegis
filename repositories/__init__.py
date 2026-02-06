"""Repository layer using Peewee ORM - data access abstraction."""

from typing import Optional, List, Dict, Any
from models.database import (
    User, Job, PaperAnalysis, ExecutionDetails, AspectEvaluation,
    ChatSession, ChatMessage, Artifact, Event,
    CachePaperAnalysis, CacheCodeExecution, CacheEvaluation
)


# ============================================================================
# User Repository
# ============================================================================

class UserRepository:
    """User data access."""
    
    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            return User.get_by_id(user_id)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        """Get user by username."""
        try:
            return User.get(User.username == username)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def exists(username: str, email: str) -> bool:
        """Check if username or email exists."""
        return (
            (User.select().where(User.username == username).exists()) or
            (User.select().where(User.email == email).exists())
        )
    
    @staticmethod
    def create(username: str, email: str, password_hash: str) -> Optional[int]:
        """Create new user. Returns user_id or None."""
        try:
            user = User.create(
                username=username,
                email=email,
                password_hash=password_hash,
                is_active=False
            )
            return user.id
        except Exception:
            return None
    
    @staticmethod
    def update_password(user_id: int, password_hash: str) -> bool:
        """Update user password. Returns True on success."""
        try:
            User.update(password_hash=password_hash).where(User.id == user_id).execute()
            return True
        except Exception:
            return False


# ============================================================================
# Job Repository
# ============================================================================

class JobRepository:
    """Job data access."""
    
    @staticmethod
    def get(job_id: str) -> Optional[Job]:
        """Get job by ID."""
        try:
            return Job.get_by_id(job_id)
        except Job.DoesNotExist:
            return None
    
    @staticmethod
    def list_all(user_id: Optional[int] = None, limit: int = 100) -> List[Job]:
        """List jobs. If user_id provided, filter by user."""
        try:
            query = Job.select()
            if user_id:
                query = query.where(Job.user == user_id)
            return list(query.order_by(Job.created_at.desc()).limit(limit))
        except Exception:
            return []
    
    @staticmethod
    def create(job_id: str, pdf_path: str, user_id: Optional[int] = None) -> bool:
        """Create new job. Returns True on success."""
        try:
            Job.create(
                id=job_id,
                pdf_path=pdf_path,
                user_id=user_id,
                status='pending',
                current_stage='pending'
            )
            return True
        except Exception:
            return False
    
    # NOTE: DO NOT ADD update_status, update_stage, or update_progress methods here.
    # All job status updates MUST go through services.job_service.update_job_status()
    # to ensure consistent logging and validation.
    # See job_service.update_job_status() - it's the single source of truth for progress updates.
    
    @staticmethod
    def update_report(job_id: str, report: dict) -> bool:
        """Update job report. Returns True on success."""
        try:
            job = Job.get_by_id(job_id)
            job.set_report(report)
            job.save()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete(job_id: str) -> bool:
        """Delete job and related records. Returns True on success."""
        try:
            # Peewee handles cascading deletes automatically
            Job.delete_by_id(job_id)
            return True
        except Exception:
            return False


# ============================================================================
# Paper Analysis Repository
# ============================================================================

class PaperAnalysisRepository:
    """Paper analysis data access."""
    
    @staticmethod
    def get(job_id: str) -> Optional[PaperAnalysis]:
        """Get paper analysis for job."""
        try:
            return PaperAnalysis.get(PaperAnalysis.job == job_id)
        except PaperAnalysis.DoesNotExist:
            return None
    
    @staticmethod
    def save(analysis: PaperAnalysis) -> bool:
        """Save paper analysis. Returns True on success."""
        try:
            analysis.save()
            return True
        except Exception:
            return False


# ============================================================================
# Execution Details Repository
# ============================================================================

class ExecutionDetailsRepository:
    """Execution details data access."""
    
    @staticmethod
    def get(job_id: str) -> Optional[ExecutionDetails]:
        """Get execution details for job."""
        try:
            return ExecutionDetails.get(ExecutionDetails.job == job_id)
        except ExecutionDetails.DoesNotExist:
            return None
    
    @staticmethod
    def save(details: ExecutionDetails) -> bool:
        """Save execution details. Returns True on success."""
        try:
            details.save()
            return True
        except Exception:
            return False


# ============================================================================
# Aspect Evaluation Repository
# ============================================================================

class AspectEvaluationRepository:
    """Aspect evaluation data access."""
    
    @staticmethod
    def list_by_job(job_id: str) -> List[AspectEvaluation]:
        """Get all evaluations for a job."""
        try:
            return list(
                AspectEvaluation.select()
                .where(AspectEvaluation.job == job_id)
                .order_by(AspectEvaluation.aspect_id)
            )
        except Exception:
            return []
    
    @staticmethod
    def save(evaluation: AspectEvaluation) -> bool:
        """Save evaluation. Returns True on success."""
        try:
            evaluation.save()
            return True
        except Exception:
            return False
    
    @staticmethod
    def save_all(evaluations: List[AspectEvaluation]) -> bool:
        """Save multiple evaluations. Returns True on success."""
        try:
            for evaluation in evaluations:
                evaluation.save()
            return True
        except Exception:
            return False


# ============================================================================
# Chat Repository
# ============================================================================

class ChatRepository:
    """Chat data access."""
    
    @staticmethod
    def get_or_create_session(job_id: str) -> int:
        """Get or create chat session for job. Returns session_id."""
        try:
            session, created = ChatSession.get_or_create(job_id=job_id)
            return session.id
        except Exception:
            return None
    
    @staticmethod
    def save_message(session_id: int, role: str, content: str) -> bool:
        """Save chat message. Returns True on success."""
        try:
            ChatMessage.create(session_id=session_id, role=role, content=content)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_history(session_id: int, limit: int = 20) -> List[ChatMessage]:
        """Get chat history. Returns messages in chronological order."""
        try:
            messages = list(
                ChatMessage.select()
                .where(ChatMessage.session == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            return list(reversed(messages))  # Chronological order
        except Exception:
            return []
    
    @staticmethod
    def clear_history(session_id: int) -> bool:
        """Delete all messages in session. Returns True on success."""
        try:
            ChatMessage.delete().where(ChatMessage.session == session_id).execute()
            return True
        except Exception:
            return False


# ============================================================================
# Artifact Repository
# ============================================================================

class ArtifactRepository:
    """Artifact data access."""
    
    @staticmethod
    def create(job_id: str, url: str, artifact_type: str, description: str = None) -> bool:
        """Create artifact. Returns True on success."""
        try:
            Artifact.create(
                job_id=job_id,
                url=url,
                artifact_type=artifact_type,
                description=description
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def list_by_job(job_id: str) -> List[Artifact]:
        """Get all artifacts for a job."""
        try:
            return list(Artifact.select().where(Artifact.job == job_id))
        except Exception:
            return []


# ============================================================================
# Event Repository
# ============================================================================

class EventRepository:
    """Event data access."""
    
    @staticmethod
    def create(job_id: str, step: str, message: str = None, severity: str = "info") -> bool:
        """Create event. Returns True on success."""
        try:
            Event.create(
                job_id=job_id,
                step=step,
                message=message,
                severity=severity
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def list_by_job(job_id: str) -> List[Event]:
        """Get all events for a job."""
        try:
            return list(
                Event.select()
                .where(Event.job_id == job_id)
                .order_by(Event.timestamp.asc())
            )
        except Exception:
            return []


# ============================================================================
# Cache Repositories
# ============================================================================

class CachePaperAnalysisRepository:
    """Cache for paper analysis by PDF hash."""
    
    @staticmethod
    def get_by_hash(pdf_hash: str) -> Optional[CachePaperAnalysis]:
        """Get cached result by PDF hash."""
        try:
            return CachePaperAnalysis.get(CachePaperAnalysis.pdf_hash == pdf_hash)
        except CachePaperAnalysis.DoesNotExist:
            return None
    
    @staticmethod
    def save(cache: CachePaperAnalysis) -> bool:
        """Save cache entry."""
        try:
            cache.save()
            return True
        except Exception:
            return False


class CacheCodeExecutionRepository:
    """Cache for code execution by repo hash."""
    
    @staticmethod
    def get(repo_url: str, repo_hash: str) -> Optional[CacheCodeExecution]:
        """Get cached result by repo hash."""
        try:
            return CacheCodeExecution.get(
                (CacheCodeExecution.repo_url == repo_url) &
                (CacheCodeExecution.repo_hash == repo_hash)
            )
        except CacheCodeExecution.DoesNotExist:
            return None
    
    @staticmethod
    def save(cache: CacheCodeExecution) -> bool:
        """Save cache entry."""
        try:
            cache.save()
            return True
        except Exception:
            return False


class CacheEvaluationRepository:
    """Cache for evaluation by paper+code hash."""
    
    @staticmethod
    def get(paper_hash: str, code_hash: str) -> Optional[CacheEvaluation]:
        """Get cached result by hashes."""
        try:
            return CacheEvaluation.get(
                (CacheEvaluation.paper_hash == paper_hash) &
                (CacheEvaluation.code_hash == code_hash)
            )
        except CacheEvaluation.DoesNotExist:
            return None
    
    @staticmethod
    def save(cache: CacheEvaluation) -> bool:
        """Save cache entry."""
        try:
            cache.save()
            return True
        except Exception:
            return False


# ============================================================================
# Aspect Repositories (from aspect plugin system Phase 1)
# ============================================================================

from .aspect_repository import AspectRepository, UserAspectRepository

__all__ = [
    'UserRepository',
    'JobRepository',
    'PaperAnalysisRepository',
    'ExecutionDetailsRepository',
    'AspectEvaluationRepository',
    'ChatRepository',
    'ArtifactRepository',
    'EventRepository',
    'CachePaperAnalysisRepository',
    'CacheCodeExecutionRepository',
    'CacheEvaluationRepository',
    'AspectRepository',
    'UserAspectRepository',
]
