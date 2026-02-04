"""Repository layer - data access abstraction."""

from typing import Optional, List
from database import get_db
from models import (
    User, Job, PaperAnalysis, ExecutionDetails, AspectEvaluation,
    ChatSession, ChatMessage
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
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT id, password_hash, username, email, is_active, created_at FROM users WHERE id = ?",
                (user_id,)
            )
            row = c.fetchone()
            conn.close()
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                is_active=row['is_active'],
                created_at=row['created_at'],
            ) if row else None
        except Exception:
            return None
    
    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        """Get user by username."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT id, password_hash, username, email, is_active, created_at FROM users WHERE username = ?",
                (username,)
            )
            row = c.fetchone()
            conn.close()
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                is_active=row['is_active'],
                created_at=row['created_at'],
            ) if row else None
        except Exception:
            return None
    
    @staticmethod
    def exists(username: str, email: str) -> bool:
        """Check if username or email exists."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            result = c.fetchone()
            conn.close()
            return result is not None
        except Exception:
            return False
    
    @staticmethod
    def create(username: str, email: str, password_hash: str) -> Optional[int]:
        """Create new user. Returns user_id or None."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 0)",
                (username, email, password_hash)
            )
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            return user_id
        except Exception:
            return None
    
    @staticmethod
    def update_password(user_id: int, password_hash: str) -> bool:
        """Update user password. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
            conn.commit()
            conn.close()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            return Job.from_row(row) if row else None
        except Exception:
            return None
    
    @staticmethod
    def list_all(user_id: Optional[int] = None, limit: int = 100) -> List[Job]:
        """List jobs. If user_id provided, filter by user."""
        try:
            conn = get_db()
            c = conn.cursor()
            if user_id:
                c.execute(
                    "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit)
                )
            else:
                c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            conn.close()
            return [Job.from_row(row) for row in rows]
        except Exception:
            return []
    
    @staticmethod
    def create(job_id: str, pdf_path: str, user_id: Optional[int] = None) -> bool:
        """Create new job. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT INTO jobs (id, pdf_path, user_id, status, current_stage) VALUES (?, ?, ?, 'pending', 'pending')",
                (job_id, pdf_path, user_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def update_status(job_id: str, status: str, progress: float = None, current_stage: str = None) -> bool:
        """Update job status/stage. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            
            if progress is not None and current_stage is not None:
                c.execute(
                    "UPDATE jobs SET status = ?, progress = ?, current_stage = ? WHERE id = ?",
                    (status, progress, current_stage, job_id)
                )
            elif progress is not None:
                c.execute(
                    "UPDATE jobs SET status = ?, progress = ? WHERE id = ?",
                    (status, progress, job_id)
                )
            elif current_stage is not None:
                c.execute(
                    "UPDATE jobs SET status = ?, current_stage = ? WHERE id = ?",
                    (status, current_stage, job_id)
                )
            else:
                c.execute(
                    "UPDATE jobs SET status = ? WHERE id = ?",
                    (status, job_id)
                )
            
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def update_stage(job_id: str, current_stage: str, progress: float = None) -> bool:
        """Update job stage. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            if progress is not None:
                c.execute(
                    "UPDATE jobs SET current_stage = ?, progress = ? WHERE id = ?",
                    (current_stage, progress, job_id)
                )
            else:
                c.execute(
                    "UPDATE jobs SET current_stage = ? WHERE id = ?",
                    (current_stage, job_id)
                )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def update_progress(job_id: str, progress: float) -> bool:
        """Update job progress. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "UPDATE jobs SET progress = ? WHERE id = ?",
                (progress, job_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def update_report(job_id: str, report: dict) -> bool:
        """Update job report. Returns True on success."""
        try:
            import json
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "UPDATE jobs SET report = ? WHERE id = ?",
                (json.dumps(report), job_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete(job_id: str) -> bool:
        """Delete job. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            # Delete related records first
            c.execute("DELETE FROM aspect_evaluations WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM execution_details WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM paper_analysis WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM chat_sessions WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM paper_analysis WHERE job_id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            return PaperAnalysis.from_row(row) if row else None
        except Exception:
            return None
    
    @staticmethod
    def save(analysis: PaperAnalysis) -> bool:
        """Save paper analysis. Returns True on success."""
        try:
            import json
            conn = get_db()
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO paper_analysis 
                   (job_id, pdf_hash, title, abstract, citations, extracted_text, 
                    claimed_results, methodology, dependencies, dataset_description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis.job_id,
                    analysis.pdf_hash,
                    analysis.title,
                    analysis.abstract,
                    json.dumps(analysis.citations) if analysis.citations else None,
                    analysis.extracted_text,
                    json.dumps(analysis.claimed_results) if analysis.claimed_results else None,
                    analysis.methodology,
                    analysis.dependencies,
                    analysis.dataset_description,
                )
            )
            conn.commit()
            conn.close()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM execution_details WHERE job_id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            return ExecutionDetails.from_row(row) if row else None
        except Exception:
            return None
    
    @staticmethod
    def save(details: ExecutionDetails) -> bool:
        """Save execution details. Returns True on success."""
        try:
            import json
            conn = get_db()
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO execution_details
                   (job_id, commands_run, stdout_combined, actual_results, dependencies_used,
                    errors_summary, discovered_files, test_info, randomness_info)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    details.job_id,
                    details.commands_run,
                    details.stdout_combined,
                    json.dumps(details.actual_results) if details.actual_results else None,
                    details.dependencies_used,
                    details.errors_summary,
                    json.dumps(details.discovered_files) if details.discovered_files else None,
                    details.test_info,
                    details.randomness_info,
                )
            )
            conn.commit()
            conn.close()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM aspect_evaluations WHERE job_id = ? ORDER BY aspect_id", (job_id,))
            rows = c.fetchall()
            conn.close()
            return [AspectEvaluation.from_row(row) for row in rows]
        except Exception:
            return []
    
    @staticmethod
    def save(evaluation: AspectEvaluation) -> bool:
        """Save evaluation. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO aspect_evaluations
                   (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    evaluation.job_id,
                    evaluation.aspect_id,
                    evaluation.name,
                    evaluation.status,
                    evaluation.evidence,
                    evaluation.paper_supports,
                    evaluation.code_supports,
                    evaluation.conclusion,
                )
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def save_all(evaluations: List[AspectEvaluation]) -> bool:
        """Save multiple evaluations. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            for eval in evaluations:
                c.execute(
                    """INSERT OR REPLACE INTO aspect_evaluations
                       (job_id, aspect_id, name, status, evidence, paper_supports, code_supports, conclusion)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        eval.job_id,
                        eval.aspect_id,
                        eval.name,
                        eval.status,
                        eval.evidence,
                        eval.paper_supports,
                        eval.code_supports,
                        eval.conclusion,
                    )
                )
            conn.commit()
            conn.close()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM chat_sessions WHERE job_id = ?", (job_id,))
            row = c.fetchone()
            if row:
                conn.close()
                return row['id']
            
            c.execute("INSERT INTO chat_sessions (job_id) VALUES (?)", (job_id,))
            conn.commit()
            session_id = c.lastrowid
            conn.close()
            return session_id
        except Exception:
            return None
    
    @staticmethod
    def save_message(session_id: int, role: str, content: str) -> bool:
        """Save chat message. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_history(session_id: int, limit: int = 20) -> List[ChatMessage]:
        """Get chat history. Returns last N messages."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            )
            rows = c.fetchall()
            conn.close()
            messages = [ChatMessage.from_row(row) for row in rows]
            return list(reversed(messages))  # Return in chronological order
        except Exception:
            return []
    
    @staticmethod
    def clear_history(session_id: int) -> bool:
        """Delete all messages in session. Returns True on success."""
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
