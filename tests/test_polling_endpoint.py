"""Tests for polling endpoint (/api/job/<id>/events).

Tests event retrieval via polling mechanism with various timestamps and filters.
"""

import json
from datetime import datetime, timedelta

import pytest

from models.database import Event, Job, User


@pytest.fixture
def auth_user(app, client):
    """Create authenticated user and return client with session."""
    import time

    unique_suffix = str(int(time.time() * 1000000))

    with app.app_context():
        user = User.create(
            username=f"testuser_{unique_suffix}", password_hash="test_hash", email=f"test_{unique_suffix}@example.com"
        )

    # Set session
    with client.session_transaction() as sess:
        sess["user_id"] = user.id

    return client, user.id


@pytest.fixture
def sample_job_with_events(app, auth_user):
    """Create a job with several events at different timestamps."""
    client, user_id = auth_user

    with app.app_context():
        # Create job
        job = Job.create(
            id="test-job-001",
            user_id=user_id,
            filename="sample.pdf",
            pdf_path="/uploads/sample.pdf",
            status="processing",
            current_stage="paper_analysis",
            progress=0.3,
        )

        # Create events at different times
        base_time = datetime.utcnow()

        event1 = Event.create(
            job_id=job.id,
            step="pdf_extracted",
            message="PDF extracted successfully",
            severity="info",
            timestamp=base_time - timedelta(seconds=10),
        )

        event2 = Event.create(
            job_id=job.id,
            step="stage_1_complete",
            message="Paper analysis complete",
            severity="info",
            timestamp=base_time - timedelta(seconds=5),
            stage_duration_ms=5000,
        )

        event3 = Event.create(
            job_id=job.id,
            step="stage_2_starting",
            message="Starting code execution",
            severity="info",
            timestamp=base_time,
        )

        return client, job, [event1, event2, event3], base_time


class TestPollingEndpoint:
    """Tests for /api/job/<id>/events polling endpoint."""

    def test_get_all_events_no_timestamp(self, sample_job_with_events):
        """Test fetching all events without 'since' parameter."""
        client, job, events, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "events" in data
        assert "completed" in data
        assert "job_status" in data

        # Should return all 3 events
        assert len(data["events"]) == 3
        assert data["events"][0]["step"] == "pdf_extracted"
        assert data["events"][1]["step"] == "stage_1_complete"
        assert data["events"][2]["step"] == "stage_2_starting"

    def test_get_events_since_timestamp(self, sample_job_with_events):
        """Test fetching events since specific timestamp."""
        client, job, events, base_time = sample_job_with_events

        # Get events since middle timestamp
        since_time = base_time - timedelta(seconds=6)
        since_iso = since_time.isoformat() + "Z"

        response = client.get(f"/api/job/{job.id}/events?since={since_iso}")
        assert response.status_code == 200

        data = json.loads(response.data)
        # Should only get events after the 'since' time
        # Should have event2 (at -5s) and event3 (at 0s)
        assert len(data["events"]) == 2
        assert data["events"][0]["step"] == "stage_1_complete"
        assert data["events"][1]["step"] == "stage_2_starting"

    def test_event_fields_format(self, sample_job_with_events):
        """Test that event fields are properly formatted."""
        client, job, events, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        event = data["events"][0]

        # Check required fields
        assert "id" in event
        assert "job_id" in event
        assert "step" in event
        assert "message" in event
        assert "severity" in event
        assert "timestamp" in event
        assert "stage_duration_ms" in event

        # Check field types
        assert isinstance(event["id"], str)
        assert isinstance(event["job_id"], str)
        assert isinstance(event["step"], str)
        assert isinstance(event["message"], str)
        assert isinstance(event["severity"], str)
        assert isinstance(event["timestamp"], str)
        assert isinstance(event["stage_duration_ms"], (int, type(None)))

        # Timestamp should be ISO format with Z
        assert event["timestamp"].endswith("Z")

    def test_polling_captures_event_with_duration(self, sample_job_with_events):
        """Test that stage_duration_ms is captured in polling response."""
        client, job, events, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        # Event 2 (stage_1_complete) has duration
        event2 = data["events"][1]
        assert event2["step"] == "stage_1_complete"
        assert event2["stage_duration_ms"] == 5000

    def test_polling_job_completion_status(self, app, auth_user):
        """Test that 'completed' flag reflects job status."""
        client, user_id = auth_user

        with app.app_context():
            # Create completed job
            job = Job.create(
                id="completed-job",
                user_id=user_id,
                filename="done.pdf",
                pdf_path="/uploads/done.pdf",
                status="completed",
                current_stage="completed",
                progress=1.0,
            )

            # Add final event
            Event.create(
                job_id=job.id,
                step="complete",
                message="Analysis complete",
                severity="info",
                timestamp=datetime.utcnow(),
            )

        response = client.get("/api/job/completed-job/events")
        data = json.loads(response.data)

        assert data["completed"] is True
        assert data["job_status"] == "completed"

    def test_polling_job_not_completed(self, sample_job_with_events):
        """Test that 'completed' flag is False for in-progress jobs."""
        client, job, _, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        assert data["completed"] is False
        assert data["job_status"] == "processing"

    def test_polling_access_control(self, app):
        """Test that users can only access their own jobs."""
        import time

        client1 = app.test_client()
        client2 = app.test_client()

        with app.app_context():
            # Create two users with unique usernames
            unique_suffix = str(int(time.time() * 1000))
            user1 = User.create(
                username=f"user1_{unique_suffix}", password_hash="hash1", email=f"user1_{unique_suffix}@example.com"
            )
            user2 = User.create(
                username=f"user2_{unique_suffix}", password_hash="hash2", email=f"user2_{unique_suffix}@example.com"
            )

            # User1 creates a job
            Job.create(
                id="user1-job",
                user_id=user1.id,
                filename="secret.pdf",
                pdf_path="/uploads/secret.pdf",
                status="processing",
            )

        # Authenticate as user1
        with client1.session_transaction() as sess:
            sess["user_id"] = user1.id

        # User1 can access their job
        response1 = client1.get("/api/job/user1-job/events")
        assert response1.status_code == 200

        # Authenticate as user2
        with client2.session_transaction() as sess:
            sess["user_id"] = user2.id

        # User2 cannot access user1's job
        response2 = client2.get("/api/job/user1-job/events")
        assert response2.status_code == 403

    def test_polling_invalid_timestamp_format(self, sample_job_with_events):
        """Test that invalid timestamp format returns error."""
        client, job, _, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events?since=invalid-date")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "Invalid timestamp" in data["error"]

    def test_polling_nonexistent_job(self, auth_user):
        """Test that accessing non-existent job returns 404."""
        client, _ = auth_user

        response = client.get("/api/job/nonexistent-job/events")
        assert response.status_code == 404

    def test_polling_unauthenticated_access(self, app):
        """Test that unauthenticated requests are denied."""
        client = app.test_client()

        response = client.get("/api/job/any-job/events")
        # Should redirect to login or return 401/403
        assert response.status_code in [301, 302, 401, 403]

    def test_polling_event_ordering(self, sample_job_with_events):
        """Test that events are returned in chronological order."""
        client, job, events, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        # Events should be ordered by timestamp (oldest first)
        for i in range(len(data["events"]) - 1):
            curr_time = datetime.fromisoformat(data["events"][i]["timestamp"].replace("Z", "+00:00"))
            next_time = datetime.fromisoformat(data["events"][i + 1]["timestamp"].replace("Z", "+00:00"))
            assert curr_time <= next_time, "Events not in chronological order"

    def test_polling_response_limit(self, app, auth_user):
        """Test that polling response respects safety limit."""
        client, user_id = auth_user

        with app.app_context():
            job = Job.create(
                id="many-events-job",
                user_id=user_id,
                filename="busy.pdf",
                pdf_path="/uploads/busy.pdf",
                status="processing",
            )

            # Create 600 events (exceeds 500 limit)
            base_time = datetime.utcnow()
            for i in range(600):
                Event.create(
                    job_id=job.id,
                    step=f"event_{i}",
                    message=f"Event {i}",
                    severity="info",
                    timestamp=base_time + timedelta(seconds=i),
                )

        response = client.get("/api/job/many-events-job/events")
        data = json.loads(response.data)

        # Should respect 500 event limit
        assert len(data["events"]) <= 500
        assert len(data["events"]) == 500  # Should be exactly at limit


class TestPollingFrontendIntegration:
    """Tests for frontend polling integration."""

    def test_polling_response_format_for_javascript(self, sample_job_with_events):
        """Test that response format is suitable for JavaScript consumption."""
        client, job, _, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        # Frontend expects these top-level keys
        assert set(data.keys()) >= {"events", "completed", "job_status"}

        # Each event should have these keys for UI rendering
        for event in data["events"]:
            assert "step" in event  # For determining UI icon/styling
            assert "message" in event  # For displaying in log
            assert "timestamp" in event  # For sorting
            assert "severity" in event  # For color coding (info/warning/error)

    def test_polling_timestamp_parsing_in_response(self, sample_job_with_events):
        """Test that timestamps in response are parseable as JavaScript Date."""
        client, job, _, _ = sample_job_with_events

        response = client.get(f"/api/job/{job.id}/events")
        data = json.loads(response.data)

        # All timestamps should be ISO format (parseable by JavaScript)
        for event in data["events"]:
            ts = event["timestamp"]
            # Should parse without error
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
