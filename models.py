"""Data models - type-safe representation of database entities."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


# ============================================================================
# User Model
# ============================================================================

@dataclass
class User:
    """User account."""
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at,
        }


# ============================================================================
# Job Models
# ============================================================================

@dataclass
class Job:
    """PDF analysis job."""
    id: str
    status: str  # pending, processing, completed, failed
    current_stage: str  # pending, paper_analysis, code_execution, evaluation, completed
    pdf_path: str
    created_at: str
    user_id: Optional[int] = None
    pdf_filename: Optional[str] = None
    progress: float = 0.0
    report: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    thumbnail_path: Optional[str] = None
    num_pages: Optional[int] = None
    completed_at: Optional[str] = None
    
    @staticmethod
    def from_row(row) -> 'Job':
        """Convert sqlite3.Row to Job."""
        report = None
        if row['report']:
            try:
                report = json.loads(row['report'])
            except:
                pass
        
        return Job(
            id=row['id'],
            user_id=row.get('user_id'),
            status=row['status'],
            current_stage=row.get('current_stage', 'pending'),
            pdf_path=row['pdf_path'],
            pdf_filename=row.get('pdf_filename'),
            progress=row.get('progress', 0.0),
            report=report,
            error_message=row.get('error_message'),
            thumbnail_path=row.get('thumbnail_path'),
            num_pages=row.get('num_pages'),
            created_at=row['created_at'],
            completed_at=row.get('completed_at'),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'status': self.status,
            'current_stage': self.current_stage,
            'progress': self.progress,
            'pdf_filename': self.pdf_filename,
            'num_pages': self.num_pages,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'thumbnail_path': self.thumbnail_path,
        }


@dataclass
class PaperAnalysis:
    """Results from stage 1: Paper analysis."""
    job_id: str
    pdf_hash: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    extracted_text: Optional[str] = None
    claimed_results: Optional[Dict[str, Any]] = None
    methodology: Optional[str] = None
    dependencies: Optional[str] = None
    dataset_description: Optional[str] = None
    created_at: Optional[str] = None
    
    @staticmethod
    def from_row(row) -> 'PaperAnalysis':
        """Convert sqlite3.Row to PaperAnalysis."""
        citations = None
        claimed_results = None
        
        if row.get('citations'):
            try:
                citations = json.loads(row['citations'])
            except:
                pass
        
        if row.get('claimed_results'):
            try:
                claimed_results = json.loads(row['claimed_results'])
            except:
                pass
        
        return PaperAnalysis(
            job_id=row['job_id'],
            pdf_hash=row.get('pdf_hash'),
            title=row.get('title'),
            abstract=row.get('abstract'),
            citations=citations,
            extracted_text=row.get('extracted_text'),
            claimed_results=claimed_results,
            methodology=row.get('methodology'),
            dependencies=row.get('dependencies'),
            dataset_description=row.get('dataset_description'),
            created_at=row.get('created_at'),
        )


@dataclass
class ExecutionDetails:
    """Results from stage 2: Code execution."""
    job_id: str
    commands_run: Optional[str] = None
    stdout_combined: Optional[str] = None
    actual_results: Optional[Dict[str, Any]] = None
    dependencies_used: Optional[str] = None
    errors_summary: Optional[str] = None
    discovered_files: Optional[List[str]] = None
    test_info: Optional[str] = None
    randomness_info: Optional[str] = None
    created_at: Optional[str] = None
    
    @staticmethod
    def from_row(row) -> 'ExecutionDetails':
        """Convert sqlite3.Row to ExecutionDetails."""
        actual_results = None
        discovered_files = None
        
        if row.get('actual_results'):
            try:
                actual_results = json.loads(row['actual_results'])
            except:
                pass
        
        if row.get('discovered_files'):
            try:
                discovered_files = json.loads(row['discovered_files'])
            except:
                pass
        
        return ExecutionDetails(
            job_id=row['job_id'],
            commands_run=row.get('commands_run'),
            stdout_combined=row.get('stdout_combined'),
            actual_results=actual_results,
            dependencies_used=row.get('dependencies_used'),
            errors_summary=row.get('errors_summary'),
            discovered_files=discovered_files,
            test_info=row.get('test_info'),
            randomness_info=row.get('randomness_info'),
            created_at=row.get('created_at'),
        )


@dataclass
class AspectEvaluation:
    """Results from stage 3: Reproducibility aspect evaluation."""
    job_id: str
    aspect_id: str
    name: str
    status: str  # yes, partial, no, unknown
    evidence: Optional[str] = None
    paper_supports: Optional[bool] = None
    code_supports: Optional[bool] = None
    conclusion: Optional[str] = None
    created_at: Optional[str] = None
    
    @staticmethod
    def from_row(row) -> 'AspectEvaluation':
        """Convert sqlite3.Row to AspectEvaluation."""
        return AspectEvaluation(
            job_id=row['job_id'],
            aspect_id=row['aspect_id'],
            name=row['name'],
            status=row['status'],
            evidence=row.get('evidence'),
            paper_supports=row.get('paper_supports'),
            code_supports=row.get('code_supports'),
            conclusion=row.get('conclusion'),
            created_at=row.get('created_at'),
        )


# ============================================================================
# Chat Models
# ============================================================================

@dataclass
class ChatSession:
    """Chat session for a job."""
    id: int
    job_id: str
    created_at: str
    
    @staticmethod
    def from_row(row) -> 'ChatSession':
        """Convert sqlite3.Row to ChatSession."""
        return ChatSession(
            id=row['id'],
            job_id=row['job_id'],
            created_at=row['created_at'],
        )


@dataclass
class ChatMessage:
    """Single chat message."""
    id: int
    session_id: int
    role: str  # "user" or "assistant"
    content: str
    created_at: str
    
    @staticmethod
    def from_row(row) -> 'ChatMessage':
        """Convert sqlite3.Row to ChatMessage."""
        return ChatMessage(
            id=row['id'],
            session_id=row['session_id'],
            role=row['role'],
            content=row['content'],
            created_at=row['created_at'],
        )
