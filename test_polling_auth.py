#!/usr/bin/env python3
"""Test polling endpoint with API key authentication."""

import sys
import json
from io import BytesIO

sys.path.insert(0, '/app')

from models.database import init_db, User
from models.api_key import APIKey
from utils.api_key_utils import generate_api_key, hash_api_key
from app import create_app

init_db()
app = create_app()

print("=== CLI POLLING AUTH TEST ===\n")

user = User.select().first()
user_id = user.id

# Create API key
api_key = generate_api_key()
key_hash, _ = hash_api_key(api_key)

APIKey.create(
    user_id=user_id,
    name="Polling Test",
    key_hash=key_hash,
    key_prefix=api_key[:8]
)

print(f"API Key: {api_key[:20]}...\n")

with app.test_client() as client:
    # Step 1: Upload PDF with API key
    print("STEP 1: Upload PDF with API key...")
    pdf_content = (
        b'%PDF-1.4\n'
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n'
        b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n'
        b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF'
    )
    
    upload_response = client.post(
        '/api/job/upload',
        data={'pdf': (BytesIO(pdf_content), 'test.pdf')},
        headers={'Authorization': f'ApiKey {api_key}'}
    )
    
    print(f"  Upload status: {upload_response.status_code}")
    if upload_response.status_code != 202:
        print(f"  ERROR: {upload_response.get_json()}")
        sys.exit(1)
    
    upload_data = upload_response.get_json()
    job_id = upload_data['job_id']
    print(f"  ✓ Job created: {job_id}\n")
    
    # Step 2: Poll job status with API key
    print("STEP 2: Poll job status with API key...")
    poll_response = client.get(
        f'/api/job/{job_id}/full',
        headers={'Authorization': f'ApiKey {api_key}'}
    )
    
    print(f"  Poll status: {poll_response.status_code}")
    
    if poll_response.status_code == 401:
        print(f"  ✗ AUTHENTICATION FAILED!")
        print(f"  Response: {poll_response.get_json()}")
        sys.exit(1)
    elif poll_response.status_code == 403:
        print(f"  ✗ FORBIDDEN (wrong user?)")
        print(f"  Response: {poll_response.get_json()}")
        sys.exit(1)
    elif poll_response.status_code != 200:
        print(f"  ✗ Unexpected status: {poll_response.status_code}")
        print(f"  Response: {poll_response.get_json()}")
        sys.exit(1)
    
    poll_data = poll_response.get_json()
    print(f"  ✓ Poll succeeded!")
    print(f"  Status: {poll_data.get('status')}")
    print(f"  Progress: {poll_data.get('progress')}")
    print(f"  Stage: {poll_data.get('current_stage')}\n")

print("=== POLLING AUTH TEST PASSED ===")
