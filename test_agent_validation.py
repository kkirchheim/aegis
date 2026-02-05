#!/usr/bin/env python3
"""Test agent endpoint validation with extra fields."""

import sys
import json
from io import BytesIO

sys.path.insert(0, '/app')

from models.database import init_db
from app import create_app

init_db()
app = create_app()

print("=== AGENT VALIDATION TEST ===\n")

# Create a test job
with app.test_client() as client:
    # First, upload a PDF to create a job
    pdf_content = (
        b'%PDF-1.4\n'
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n'
        b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n'
        b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF'
    )
    
    # Create session
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    upload_response = client.post(
        '/api/job/upload',
        data={'pdf': (BytesIO(pdf_content), 'test.pdf')}
    )
    
    job_id = upload_response.get_json()['job_id']
    print(f"Created job: {job_id}\n")
    
    # Test 1: Agent log with exact fields (should work)
    print("TEST 1: Agent log with exact fields")
    response = client.post(
        '/api/agent/log',
        json={
            'job_id': job_id,
            'message': 'Test message'
        }
    )
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.get_json()}\n")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    # Test 2: Agent log with extra fields (should now work, not 422)
    print("TEST 2: Agent log with EXTRA fields (the problem we fixed)")
    response = client.post(
        '/api/agent/log',
        json={
            'job_id': job_id,
            'message': 'Test with extras',
            'extra_field_1': 'should be ignored',
            'extra_field_2': {'nested': 'value'},
            'another_extra': 42
        }
    )
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.get_json()}\n")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.get_json()}"
    print("  ✓ Extra fields accepted (not 422)!\n")
    
    # Test 3: Agent execution with extra fields
    print("TEST 3: Agent execution with EXTRA fields")
    response = client.post(
        '/api/agent/execution',
        json={
            'job_id': job_id,
            'commands_run': 'echo hello',
            'stdout_combined': 'hello\n',
            'mystery_field': 'unknown to schema',
            'future_feature': {'data': 'v2 format'}
        }
    )
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.get_json()}\n")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("  ✓ Extra fields accepted!\n")
    
    # Test 4: Agent complete with extra fields
    print("TEST 4: Agent complete with EXTRA fields")
    response = client.post(
        '/api/agent/complete',
        json={
            'job_id': job_id,
            'success': True,
            'message': 'Done!',
            'future_stats': {'iterations': 3, 'duration_ms': 5000}
        }
    )
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.get_json()}\n")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("  ✓ Extra fields accepted!\n")
    
    # Test 5: Missing required field (should still be 422)
    print("TEST 5: Agent log missing required field (job_id)")
    response = client.post(
        '/api/agent/log',
        json={
            'message': 'No job_id!'
        }
    )
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.get_json()}\n")
    assert response.status_code == 422, f"Expected 422 for missing job_id, got {response.status_code}"
    print("  ✓ Missing required field correctly returns 422!\n")

print("=== ALL VALIDATION TESTS PASSED ===")
