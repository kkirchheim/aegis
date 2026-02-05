"""
Pytest configuration and fixtures for Paper Reproducibility Checker tests.

This conftest.py provides:
1. In-memory SQLite database for each test
2. Fresh database and admin user per test
3. Flask test client with proper setup/teardown
4. Session fixtures for authenticated tests
5. User management fixtures
6. Pytest markers for test categorization
7. Common test fixtures for DRY testing
"""

import sys
import os
import pytest
import sqlite3
import tempfile

# Set dummy API key for testing to avoid import-time errors
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-key-for-pytest"


# ============================================================================
# PYTEST MARKERS CONFIGURATION
# ============================================================================
def pytest_configure(config):
    """Register pytest markers for test categorization."""
    config.addinivalue_line("markers", "unit: mark test as unit test (fast, mocked dependencies)")
    config.addinivalue_line("markers", "integration: mark test as integration test (slower, real services)")
    config.addinivalue_line("markers", "slow: mark test as slow (skip with -m 'not slow')")
    config.addinivalue_line("markers", "db: mark test as database test (requires database)")
    config.addinivalue_line("markers", "api: mark test as API endpoint test")
    config.addinivalue_line("markers", "auth: mark test as authentication test")
    config.addinivalue_line("markers", "admin: mark test as admin management test")
    config.addinivalue_line("markers", "event: mark test as event/streaming test")

# Add parent directory to path so 'app' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from database import init_db, get_db
from services.auth_service import hash_password, create_user, get_user_by_username
from app import create_app


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to use in-memory database before each test."""
    # Use file-based temp database instead of :memory: to avoid connection isolation issues
    import tempfile
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    
    original_db = Config.DATABASE
    Config.DATABASE = temp_db_path
    
    # Reinitialize Peewee database to use the new temp database file
    from models.database import db
    if not db.is_closed():
        db.close()
    db.init(temp_db_path)
    
    # Set SSE timeout to 2 seconds for tests (instead of default 30s)
    original_sse_timeout = os.environ.get('SSE_TIMEOUT_SECONDS')
    os.environ['SSE_TIMEOUT_SECONDS'] = '2'
    
    yield
    
    Config.DATABASE = original_db
    
    # Restore original SSE timeout
    if original_sse_timeout is not None:
        os.environ['SSE_TIMEOUT_SECONDS'] = original_sse_timeout
    else:
        os.environ.pop('SSE_TIMEOUT_SECONDS', None)
    
    # Cleanup temp database file
    try:
        os.unlink(temp_db_path)
    except:
        pass


@pytest.fixture
def app():
    """Create a Flask app instance for testing."""
    # Use the temp database configured above
    app = create_app()
    app.config['TESTING'] = True
    
    with app.app_context():
        # Initialize fresh database
        init_db()
    
    yield app


@pytest.fixture
def client(app):
    """Create a test client with fresh database."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Provide Flask app context for database operations."""
    with app.app_context():
        yield
        # Clear all tables after test
        try:
            conn = get_db()
            c = conn.cursor()
            
            # Get all table names
            c.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in c.fetchall()]
            
            # Drop all tables
            for table in tables:
                try:
                    c.execute(f"DROP TABLE IF EXISTS {table}")
                except:
                    pass
            
            conn.commit()
            conn.close()
        except:
            pass


@pytest.fixture
def test_user_credentials():
    """Provide test user credentials."""
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword123!'
    }


@pytest.fixture
def admin_user_credentials():
    """Provide test admin credentials."""
    return {
        'username': 'admin',
        'email': 'admin@example.com',
        'password': 'AdminPassword123!'
    }


@pytest.fixture
def create_test_user(client, app):
    """Factory fixture to create test users."""
    def _create_user(username, email, password, is_active=True):
        with app.app_context():
            # Use Peewee ORM to create user (compatible with require_admin decorator)
            from models.database import User
            
            password_hash = hash_password(password)
            
            # Create user via Peewee ORM
            user = User.create(
                username=username,
                email=email,
                password_hash=password_hash,
                is_active=is_active
            )
            return user.id
    
    return _create_user


@pytest.fixture
def authenticated_user(client, app, create_test_user, test_user_credentials):
    """Create and authenticate a test user."""
    user_id = create_test_user(
        test_user_credentials['username'],
        test_user_credentials['email'],
        test_user_credentials['password'],
        is_active=True
    )
    
    # Set session
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = test_user_credentials['username']
    
    return client


@pytest.fixture
def authenticated_admin(client, app, create_test_user, admin_user_credentials):
    """Create and authenticate an admin user."""
    user_id = create_test_user(
        admin_user_credentials['username'],
        admin_user_credentials['email'],
        admin_user_credentials['password'],
        is_active=True
    )
    
    # Set session
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = admin_user_credentials['username']
    
    return client


@pytest.fixture
def admin_user(client, app):
    """Create and authenticate an admin user (for integration tests).
    
    Returns a Flask test client with admin session.
    Uses the default admin user created by create_default_admin_user.
    """
    with app.app_context():
        from models.database import User
        
        # Get the existing admin user (created by create_default_admin_user)
        admin_user = User.get(User.username == 'admin')
        
        # Set session - username='admin' makes user admin
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['username'] = 'admin'
    
    return client


@pytest.fixture
def test_user(app, create_test_user, test_user_credentials, request):
    """Create a test user and return their data.
    
    Each test gets a unique user to avoid UNIQUE constraint violations.
    """
    import uuid
    
    # Generate unique username and email for this test
    unique_id = str(uuid.uuid4())[:8]
    username = f"testuser_{unique_id}"
    email = f"testuser_{unique_id}@example.com"
    
    user_id = create_test_user(
        username,
        email,
        test_user_credentials['password'],
        is_active=True
    )
    
    return {
        'id': user_id,
        'username': username,
        'email': email,
        'password': test_user_credentials['password'],
        'is_active': True
    }


@pytest.fixture
def test_user_creds(test_user_credentials):
    """Provide test user credentials."""
    return test_user_credentials


@pytest.fixture
def inactive_user(app, create_test_user, request):
    """Create an inactive test user and return their data."""
    import uuid
    
    # Generate unique username and email to avoid UNIQUE constraint violations
    unique_id = str(uuid.uuid4())[:8]
    username = f"inactive_user_{unique_id}"
    email = f"inactive_{unique_id}@example.com"
    
    user_id = create_test_user(
        username,
        email,
        "InactivePass123!",
        is_active=False
    )
    
    return {
        'id': user_id,
        'username': username,
        'email': email,
        'is_active': False
    }


@pytest.fixture
def active_user(app, create_test_user, request):
    """Create an active test user and return their data."""
    import uuid
    
    # Generate unique username and email to avoid UNIQUE constraint violations
    unique_id = str(uuid.uuid4())[:8]
    username = f"active_user_{unique_id}"
    email = f"active_{unique_id}@example.com"
    
    user_id = create_test_user(
        username,
        email,
        "ActivePass123!",
        is_active=True
    )
    
    return {
        'id': user_id,
        'username': username,
        'email': email,
        'is_active': True
    }


@pytest.fixture
def unauthenticated_client(client):
    """Ensure client has no session."""
    with client.session_transaction() as sess:
        sess.clear()
    return client


@pytest.fixture
def multiple_users(client, app, create_test_user):
    """Create multiple test users for multi-user testing."""
    users = []
    for i in range(3):
        user_id = create_test_user(
            f"user{i+1}",
            f"user{i+1}@example.com",
            f"Password{i+1}!",
            is_active=True
        )
        users.append({
            'id': user_id,
            'username': f"user{i+1}",
            'email': f"user{i+1}@example.com",
            'password': f"Password{i+1}!"
        })
    
    return users


# ============================================================================
# NEW: Test Database and ORM Fixtures
# ============================================================================

@pytest.fixture
def peewee_test_db(app):
    """Provide in-memory Peewee database for testing.
    
    This fixture sets up a test database using Peewee ORM,
    with all models created and ready for use.
    """
    from models.database import init_db, db, User, Job, Event
    from models.database import PaperAnalysis, ExecutionDetails, AspectEvaluation
    
    with app.app_context():
        # Initialize database with all tables
        init_db()
        
        yield db
        
        # Cleanup: close database after test
        try:
            db.close()
        except:
            pass


@pytest.fixture
def authenticated_user_id(authenticated_user):
    """Extract user_id from authenticated_user session."""
    with authenticated_user.session_transaction() as sess:
        return sess.get('user_id')


@pytest.fixture
def create_test_job(app, peewee_test_db, authenticated_user_id):
    """Factory fixture to create test jobs in Peewee database."""
    from models.database import Job, User
    import uuid
    
    created_job_ids = []
    
    def _create_job(job_id=None, user_id=None, status="pending", current_stage="pending"):
        with app.app_context():
            # Generate unique job ID if not provided
            if job_id is None:
                job_id = str(uuid.uuid4())
            
            # Use authenticated user's ID by default
            if user_id is None:
                user_id = authenticated_user_id
            
            # Clean up any existing job with this ID
            try:
                Job.delete().where(Job.id == job_id).execute()
            except:
                pass
            
            created_job_ids.append(job_id)
            
            job = Job.create(
                id=job_id,
                user_id=user_id,
                status=status,
                current_stage=current_stage,
                pdf_path="/test/path/paper.pdf",
                pdf_filename="paper.pdf",
                progress=0.0,
            )
            return job
    
    yield _create_job
    
    # Cleanup after test
    with app.app_context():
        for job_id in created_job_ids:
            try:
                Job.delete().where(Job.id == job_id).execute()
            except:
                pass


@pytest.fixture(autouse=True)
def cleanup_sse_queues():
    """SSE queues fixture (deprecated - now using polling).
    
    This fixture is kept for backward compatibility but does nothing
    since we switched from SSE to polling architecture.
    """
    yield


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing.
    
    Provides a mock Anthropic API client that can be injected into services.
    """
    from unittest.mock import MagicMock
    
    mock_llm = MagicMock()
    
    # Configure common responses
    mock_llm.extract.return_value = {
        "title": "Test Paper Title",
        "abstract": "Test abstract",
        "methodology": "Test methodology",
    }
    
    mock_llm.analyze.return_value = {
        "key_findings": ["Finding 1", "Finding 2"],
        "reproducibility_score": 0.75,
    }
    
    mock_llm.think.return_value = "Agent thinking about the problem..."
    
    return mock_llm


@pytest.fixture
def mock_docker_service():
    """Mock Docker service for testing.
    
    Provides a mock Docker client for container operations.
    """
    from unittest.mock import MagicMock
    
    mock_docker = MagicMock()
    
    # Configure common responses
    mock_docker.spawn_agent.return_value = "container_abc123"
    mock_docker.wait_for_completion.return_value = 0  # Success exit code
    mock_docker.get_logs.return_value = "Container execution logs"
    mock_docker.cleanup.return_value = True
    
    return mock_docker


@pytest.fixture
def authenticated_client_with_fixtures(client, app, create_test_user, peewee_test_db):
    """Create authenticated test client with database fixtures ready.
    
    Combines authentication with database fixtures for integration testing.
    """
    user_id = create_test_user(
        "testuser",
        "testuser@example.com",
        "TestPassword123!",
        is_active=True
    )
    
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "testuser"
    
    return client


@pytest.fixture
def flask_app_with_mocks(app, mock_llm_provider, mock_docker_service):
    """Flask app with mocked services injected.
    
    Provides a Flask app with all external dependencies mocked,
    ready for API endpoint testing.
    """
    # Inject mocks into app context if needed
    app.llm_provider = mock_llm_provider
    app.docker_service = mock_docker_service
    
    return app


# ============================================================================
# NEW: Event and Message Fixtures
# ============================================================================

@pytest.fixture
def mock_event_queues():
    """Provide mock SSE event queues for testing."""
    return {
        "job123": [],
        "job456": [],
    }


@pytest.fixture
def create_test_event(app, peewee_test_db):
    """Factory fixture to create test events."""
    from models.database import Event, Job
    
    def _create_event(job_id, step, message="Test", severity="info"):
        with app.app_context():
            job = Job.get_by_id(job_id) if job_id else None
            if job:
                event = Event.create(
                    job=job,
                    step=step,
                    message=message,
                    severity=severity,
                )
                return event
            return None
    
    return _create_event


# ============================================================================
# NEW: Service Fixtures
# ============================================================================

@pytest.fixture
def mock_analysis_service(mock_llm_provider):
    """Mock analysis service for testing."""
    from unittest.mock import MagicMock
    
    mock_service = MagicMock()
    mock_service.analyze.return_value = {
        "title": "Test Paper",
        "abstract": "Test abstract",
        "citations": [{"title": "Ref 1"}, {"title": "Ref 2"}],
    }
    
    return mock_service


@pytest.fixture
def mock_evaluation_service():
    """Mock evaluation service for testing."""
    from unittest.mock import MagicMock
    
    mock_service = MagicMock()
    mock_service.evaluate.return_value = {
        "score": 0.85,
        "aspects": [
            {"name": "Code Availability", "status": "yes"},
            {"name": "Reproducible Results", "status": "partial"},
        ],
    }
    
    return mock_service


@pytest.fixture
def mock_job_service(peewee_test_db):
    """Mock job service for testing."""
    from unittest.mock import MagicMock
    
    mock_service = MagicMock()
    mock_service.update_job_status.return_value = True
    mock_service.get_job.return_value = {
        "id": "job123",
        "status": "processing",
        "progress": 0.5,
    }
    
    return mock_service


@pytest.fixture
def mock_event_dispatcher(mock_event_queues, mock_job_service):
    """Mock event dispatcher for testing."""
    from unittest.mock import MagicMock
    from services.event_dispatcher import EventDispatcher
    
    dispatcher = EventDispatcher(
        event_queues=mock_event_queues,
        job_service=mock_job_service,
    )
    
    return dispatcher


# ============================================================================
# NEW: Job API Testing Fixtures
# ============================================================================

@pytest.fixture
def test_pdf_file():
    """Provide a mock PDF file for testing file uploads."""
    from io import BytesIO
    
    # Create a minimal valid PDF (PDF header + EOF marker)
    pdf_content = b"""%PDF-1.4
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
<< >>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000229 00000 n
0000000310 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
392
%%EOF"""
    
    return BytesIO(pdf_content)


@pytest.fixture
def other_user(client, app, create_test_user):
    """Create and authenticate a second test user for multi-user testing."""
    user_id = create_test_user(
        "otheruser",
        "otheruser@example.com",
        "OtherPassword123!",
        is_active=True
    )
    
    # Set session for second user
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "otheruser"
    
    return client


@pytest.fixture
def test_job(authenticated_user, create_test_job, app):
    """Create a test job for the authenticated user."""
    with app.app_context():
        with authenticated_user.session_transaction() as sess:
            user_id = sess.get('user_id')
        
        job = create_test_job(user_id=user_id)
        
        # Return job as dictionary with id
        return {
            "id": str(job.id),
            "user_id": job.user_id,
            "status": job.status,
            "current_stage": job.current_stage,
        }


@pytest.fixture
def test_job_with_chat(authenticated_user, create_test_job, app):
    """Create a test job with chat messages for the authenticated user."""
    from models.database import ChatSession, ChatMessage
    
    with app.app_context():
        with authenticated_user.session_transaction() as sess:
            user_id = sess.get('user_id')
        
        job = create_test_job(user_id=user_id)
        
        # Create a chat session for this job
        chat_session = ChatSession.create(job=job)
        
        # Create some chat messages
        ChatMessage.create(
            session=chat_session,
            role="user",
            content="What are the main findings of this paper?"
        )
        ChatMessage.create(
            session=chat_session,
            role="assistant",
            content="The main findings are..."
        )
        
        # Return job as dictionary with id
        return {
            "id": str(job.id),
            "user_id": job.user_id,
            "status": job.status,
            "current_stage": job.current_stage,
        }
