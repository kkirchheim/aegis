"""Peewee ORM models for Paper Reproducibility Checker database."""

import json
from datetime import datetime
from peewee import *
from config import Config

# Database initialization
db = SqliteDatabase(Config.DATABASE)


class BaseModel(Model):
    """Base model for all database models."""
    class Meta:
        database = db


# ============================================================================
# Authentication
# ============================================================================

class User(BaseModel):
    """User account."""
    username = CharField(unique=True)
    email = CharField(unique=True)
    password_hash = CharField()
    is_active = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'users'


# ============================================================================
# Job Management
# ============================================================================

class Job(BaseModel):
    """PDF analysis job."""
    id = CharField(primary_key=True)
    user = ForeignKeyField(User, backref='jobs', null=True)
    status = CharField(default='pending')  # pending, processing, completed, failed
    current_stage = CharField(default='pending')  # pending, paper_analysis, code_execution, evaluation, completed
    progress = FloatField(default=0.0)
    pdf_path = CharField()
    pdf_filename = CharField(null=True)
    report = TextField(null=True)  # JSON string
    error_message = TextField(null=True)
    thumbnail_path = CharField(null=True)
    num_pages = IntegerField(null=True)
    created_at = DateTimeField(default=datetime.now)
    completed_at = DateTimeField(null=True)

    class Meta:
        table_name = 'jobs'
        indexes = (
            (('user', 'created_at'), False),  # Query jobs by user
        )

    def get_report(self) -> dict:
        """Parse report JSON."""
        if not self.report:
            return {}
        try:
            return json.loads(self.report)
        except:
            return {}

    def set_report(self, data: dict):
        """Set report as JSON."""
        self.report = json.dumps(data)


class Artifact(BaseModel):
    """Code artifacts discovered in paper."""
    job = ForeignKeyField(Job, backref='artifacts')
    url = CharField()
    artifact_type = CharField()  # github_repo, code_snippet, dataset, etc.
    description = TextField(null=True)

    class Meta:
        table_name = 'artifacts'


class Event(BaseModel):
    """Job event for SSE streaming."""
    job = ForeignKeyField(Job, backref='events')
    step = CharField()
    message = TextField(null=True)
    severity = CharField(default='info')  # info, warning, error
    timestamp = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'events'
        indexes = (
            (('job', 'timestamp'), False),
        )


# ============================================================================
# Analysis Results
# ============================================================================

class PaperAnalysis(BaseModel):
    """Stage 1: PDF extraction and analysis results."""
    job = ForeignKeyField(Job, backref='paper_analysis', unique=True)
    pdf_hash = CharField(null=True)
    title = CharField(null=True)
    abstract = TextField(null=True)
    citations = TextField(null=True)  # JSON list
    extracted_text = TextField(null=True)
    claimed_results = TextField(null=True)  # JSON
    methodology = TextField(null=True)
    dependencies = TextField(null=True)
    dataset_description = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'paper_analysis'

    def get_citations(self) -> list:
        """Parse citations JSON."""
        if not self.citations:
            return []
        try:
            return json.loads(self.citations)
        except:
            return []

    def set_citations(self, data: list):
        """Set citations as JSON."""
        self.citations = json.dumps(data)


class ExecutionDetails(BaseModel):
    """Stage 2: Code execution results."""
    job = ForeignKeyField(Job, backref='execution_details', unique=True)
    commands_run = TextField(null=True)
    stdout_combined = TextField(null=True)
    actual_results = TextField(null=True)  # JSON
    dependencies_used = TextField(null=True)
    errors_summary = TextField(null=True)
    discovered_files = TextField(null=True)  # JSON list
    test_info = TextField(null=True)
    randomness_info = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'execution_details'

    def get_actual_results(self) -> dict:
        """Parse actual_results JSON."""
        if not self.actual_results:
            return {}
        try:
            return json.loads(self.actual_results)
        except:
            return {}

    def get_discovered_files(self) -> list:
        """Parse discovered_files JSON."""
        if not self.discovered_files:
            return []
        try:
            return json.loads(self.discovered_files)
        except:
            return []


class AspectEvaluation(BaseModel):
    """Stage 3: Reproducibility aspect evaluation."""
    job = ForeignKeyField(Job, backref='aspect_evaluations')
    aspect_id = CharField()
    name = CharField()
    status = CharField()  # yes, partial, no, unknown
    evidence = TextField(null=True)
    paper_supports = BooleanField(null=True)
    code_supports = BooleanField(null=True)
    conclusion = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'aspect_evaluations'
        indexes = (
            (('job', 'aspect_id'), True),  # Unique per job/aspect
        )


# ============================================================================
# Caching
# ============================================================================

class CachePaperAnalysis(BaseModel):
    """Cached stage 1 results by PDF hash."""
    pdf_hash = CharField(unique=True)
    title = CharField(null=True)
    abstract = TextField(null=True)
    citations = TextField(null=True)  # JSON
    extracted_text = TextField(null=True)
    claimed_results = TextField(null=True)  # JSON
    methodology = TextField(null=True)
    dependencies = TextField(null=True)
    dataset_description = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'cache_paper_analysis'


class CacheCodeExecution(BaseModel):
    """Cached stage 2 results by repo hash."""
    repo_url = CharField()
    repo_hash = CharField()
    commands_run = TextField(null=True)
    stdout_combined = TextField(null=True)
    actual_results = TextField(null=True)  # JSON
    dependencies_used = TextField(null=True)
    errors_summary = TextField(null=True)
    discovered_files = TextField(null=True)  # JSON
    test_info = TextField(null=True)
    randomness_info = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'cache_code_execution'
        indexes = (
            (('repo_url', 'repo_hash'), True),  # Unique key
        )


class CacheEvaluation(BaseModel):
    """Cached stage 3 results by paper+code hash."""
    paper_hash = CharField()
    code_hash = CharField()
    evaluations = TextField()  # JSON
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'cache_evaluation'
        indexes = (
            (('paper_hash', 'code_hash'), True),  # Unique key
        )


# ============================================================================
# Chat
# ============================================================================

class ChatSession(BaseModel):
    """Chat session for interactive Q&A about a job."""
    job = ForeignKeyField(Job, backref='chat_sessions', unique=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'chat_sessions'


class ChatMessage(BaseModel):
    """Single message in chat session."""
    session = ForeignKeyField(ChatSession, backref='messages')
    role = CharField()  # user or assistant
    content = TextField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'chat_messages'
        indexes = (
            (('session', 'created_at'), False),
        )


# ============================================================================
# Database Initialization
# ============================================================================

def init_db(app_logger=None):
    """Initialize database and create all tables."""
    db.connect()
    
    models = [
        User, Job, Artifact, Event,
        PaperAnalysis, ExecutionDetails, AspectEvaluation,
        CachePaperAnalysis, CacheCodeExecution, CacheEvaluation,
        ChatSession, ChatMessage,
    ]
    
    db.create_tables(models, safe=True)
    
    if app_logger:
        app_logger.info("✓ Database initialized successfully")


def get_db_connection():
    """Get database connection."""
    return db
