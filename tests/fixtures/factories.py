"""Test data factories for creating test objects in a DRY manner.

This module provides factory functions for creating test users, jobs, events,
and other domain objects without repeating setup logic across tests.
"""

import uuid
import os
import sys
import tempfile
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))


def create_test_user(app, create_test_user_fixture, username="testuser", email=None, password="TestPass123!"):
    """Factory to create a test user.
    
    Args:
        app: Flask application instance (for context)
        create_test_user_fixture: The pytest fixture function from conftest
        username: Username for the test user (default: "testuser")
        email: Email address (default: {username}@example.com)
        password: Password (default: "TestPass123!")
    
    Returns:
        user_id: ID of created user
    """
    if email is None:
        email = f"{username}@example.com"
    
    user_id = create_test_user_fixture(username, email, password, is_active=True)
    return user_id


def create_test_job(app, peewee_test_db, user_id=None, job_id=None, status="pending", 
                    current_stage="pending", pdf_filename="test.pdf"):
    """Factory to create a test job.
    
    Args:
        app: Flask application instance (for context)
        peewee_test_db: Peewee database fixture
        user_id: User ID to associate with job
        job_id: Custom job ID (generated if None)
        status: Job status (default: "pending")
        current_stage: Current processing stage (default: "pending")
        pdf_filename: Name of PDF file (default: "test.pdf")
    
    Returns:
        job: Created Job instance
    """
    from models.database import Job
    
    if job_id is None:
        job_id = str(uuid.uuid4())
    
    with app.app_context():
        # Clean up any existing job with this ID
        try:
            Job.delete().where(Job.id == job_id).execute()
        except:
            pass
        
        job = Job.create(
            id=job_id,
            user_id=user_id,
            status=status,
            current_stage=current_stage,
            pdf_path=f"/test/path/{pdf_filename}",
            pdf_filename=pdf_filename,
            progress=0.0,
        )
        return job


def create_test_event(app, peewee_test_db, job_id, step="test_step", 
                      message="Test event", severity="info"):
    """Factory to create a test event.
    
    Args:
        app: Flask application instance (for context)
        peewee_test_db: Peewee database fixture
        job_id: Associated job ID
        step: Processing step name (default: "test_step")
        message: Event message (default: "Test event")
        severity: Severity level (default: "info")
    
    Returns:
        event: Created Event instance, or None if job not found
    """
    from models.database import Event, Job
    
    with app.app_context():
        try:
            job = Job.get_by_id(job_id)
            event = Event.create(
                job=job,
                step=step,
                message=message,
                severity=severity,
            )
            return event
        except:
            return None


def create_test_pdf_file(filename="test.pdf", content=None):
    """Factory to create a temporary test PDF file.
    
    Args:
        filename: Name of the file (default: "test.pdf")
        content: Content to write (default: minimal PDF)
    
    Returns:
        file_path: Path to created temporary file
    """
    if content is None:
        # Minimal valid PDF content
        content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
0000000301 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
395
%%EOF
"""
    
    temp_file = tempfile.NamedTemporaryFile(
        suffix=f".pdf" if filename.endswith(".pdf") else f".{filename.split('.')[-1]}",
        delete=False,
        prefix="test_"
    )
    temp_file.write(content)
    temp_file.close()
    
    return temp_file.name


def create_test_auth_headers(client, username="testuser", password="TestPass123!"):
    """Factory to create authentication headers for API calls.
    
    Args:
        client: Flask test client
        username: Username for login
        password: Password for login
    
    Returns:
        headers: Dictionary with authorization headers
    """
    # For session-based auth, this would set up a session
    # For token-based auth, this would return Bearer token in headers
    
    # This is a placeholder; actual implementation depends on auth mechanism
    return {
        "Authorization": f"Bearer test-token-for-{username}"
    }


class UserFactory:
    """Factory class for creating test users with fluent API."""
    
    def __init__(self, app, create_test_user_fixture):
        self.app = app
        self.create_test_user_fixture = create_test_user_fixture
        self.username = "testuser"
        self.email = "testuser@example.com"
        self.password = "TestPass123!"
        self.is_active = True
    
    def with_username(self, username):
        """Set username."""
        self.username = username
        return self
    
    def with_email(self, email):
        """Set email."""
        self.email = email
        return self
    
    def with_password(self, password):
        """Set password."""
        self.password = password
        return self
    
    def inactive(self):
        """Mark user as inactive."""
        self.is_active = False
        return self
    
    def build(self):
        """Create the user with current configuration."""
        user_id = self.create_test_user_fixture(
            self.username, 
            self.email, 
            self.password, 
            is_active=self.is_active
        )
        return user_id


class JobFactory:
    """Factory class for creating test jobs with fluent API."""
    
    def __init__(self, app, peewee_test_db, user_id=None):
        self.app = app
        self.peewee_test_db = peewee_test_db
        self.user_id = user_id
        self.job_id = str(uuid.uuid4())
        self.status = "pending"
        self.current_stage = "pending"
        self.pdf_filename = "test.pdf"
    
    def with_status(self, status):
        """Set job status."""
        self.status = status
        return self
    
    def with_stage(self, stage):
        """Set current processing stage."""
        self.current_stage = stage
        return self
    
    def with_pdf(self, filename):
        """Set PDF filename."""
        self.pdf_filename = filename
        return self
    
    def build(self):
        """Create the job with current configuration."""
        from models.database import Job
        
        with self.app.app_context():
            job = Job.create(
                id=self.job_id,
                user_id=self.user_id,
                status=self.status,
                current_stage=self.current_stage,
                pdf_path=f"/test/path/{self.pdf_filename}",
                pdf_filename=self.pdf_filename,
                progress=0.0,
            )
            return job
