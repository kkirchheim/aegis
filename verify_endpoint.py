#!/usr/bin/env python3
"""
Manual verification script for polling endpoint.
Tests without requiring pytest to be installed.
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set dummy API key for testing
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-key-for-verification"

def verify_endpoint():
    """Verify the polling endpoint exists and works correctly."""
    from app import create_app
    from models.database import User, Job, Event
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.app_context():
        # Create test user
        import time
        unique_suffix = str(int(time.time() * 1000000))
        user = User.create(
            username=f"testuser_{unique_suffix}",
            password_hash="test_hash",
            email=f"test_{unique_suffix}@example.com"
        )
        print(f"✓ Created test user: {user.username}")
        
        # Create test job
        job_id = f"test-job-{unique_suffix}"
        job = Job.create(
            id=job_id,
            user_id=user.id,
            filename="test.pdf",
            pdf_path="/uploads/test.pdf",
            status="processing",
            current_stage="paper_analysis",
            progress=0.3
        )
        print(f"✓ Created test job: {job.id}")
        
        # Create test events
        base_time = datetime.utcnow()
        
        event1 = Event.create(
            job_id=job.id,
            step="pdf_extracted",
            message="PDF extracted successfully",
            severity="info",
            timestamp=base_time - timedelta(seconds=10)
        )
        
        event2 = Event.create(
            job_id=job.id,
            step="stage_1_complete",
            message="Paper analysis complete",
            severity="info",
            timestamp=base_time - timedelta(seconds=5),
            stage_duration_ms=5000
        )
        
        event3 = Event.create(
            job_id=job.id,
            step="stage_2_starting",
            message="Starting code execution",
            severity="info",
            timestamp=base_time
        )
        print(f"✓ Created 3 test events")
    
    # Create test client
    client = app.test_client()
    
    # Set session
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
    
    print("\n--- Testing GET /api/job/<id>/events ---")
    
    # Test 1: Get all events without timestamp filter
    print("\nTest 1: Get all events (no timestamp filter)")
    response = client.get(f"/api/job/{job_id}/events")
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = json.loads(response.data)
        print(f"  ✓ Response keys: {list(data.keys())}")
        print(f"  ✓ Event count: {len(data.get('events', []))}")
        print(f"  ✓ Completed: {data.get('completed')}")
        print(f"  ✓ Job status: {data.get('job_status')}")
        
        if len(data.get('events', [])) > 0:
            event = data['events'][0]
            print(f"  ✓ First event fields: {list(event.keys())}")
            print(f"  ✓ Timestamp format: {event.get('timestamp', 'N/A')}")
    else:
        print(f"  ✗ Expected 200, got {response.status_code}")
        print(f"  Response: {response.data}")
    
    # Test 2: Get events with timestamp filter
    print("\nTest 2: Get events with 'since' parameter")
    since_time = base_time - timedelta(seconds=6)
    since_iso = since_time.isoformat() + 'Z'
    response = client.get(f"/api/job/{job_id}/events?since={since_iso}")
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = json.loads(response.data)
        print(f"  ✓ Event count: {len(data.get('events', []))}")
        if len(data.get('events', [])) > 0:
            events = data['events']
            for i, event in enumerate(events):
                print(f"  Event {i}: {event.get('step')} at {event.get('timestamp')}")
    else:
        print(f"  ✗ Expected 200, got {response.status_code}")
        print(f"  Response: {response.data}")
    
    # Test 3: Invalid timestamp format
    print("\nTest 3: Invalid timestamp format")
    response = client.get(f"/api/job/{job_id}/events?since=invalid-date")
    print(f"  Status: {response.status_code}")
    if response.status_code == 400:
        data = json.loads(response.data)
        print(f"  ✓ Error message: {data.get('error', 'N/A')}")
    else:
        print(f"  ✗ Expected 400, got {response.status_code}")
    
    # Test 4: Non-existent job
    print("\nTest 4: Non-existent job")
    response = client.get(f"/api/job/nonexistent-job/events")
    print(f"  Status: {response.status_code}")
    if response.status_code == 404:
        data = json.loads(response.data)
        print(f"  ✓ Error message: {data.get('error', 'N/A')}")
    else:
        print(f"  ✗ Expected 404, got {response.status_code}")
    
    # Test 5: Unauthenticated access
    print("\nTest 5: Unauthenticated access")
    unauthenticated_client = app.test_client()
    response = unauthenticated_client.get(f"/api/job/{job_id}/events")
    print(f"  Status: {response.status_code}")
    if response.status_code == 401:
        data = json.loads(response.data)
        print(f"  ✓ Error message: {data.get('error', 'N/A')}")
    else:
        print(f"  ✗ Expected 401, got {response.status_code}")
    
    print("\n✓ Endpoint verification complete!")

if __name__ == "__main__":
    try:
        verify_endpoint()
    except Exception as e:
        print(f"✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
