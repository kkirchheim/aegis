#!/usr/bin/env python3
"""Test CLI authentication with API key."""

import sys
import os

# Add app directory to path
sys.path.insert(0, '/app')

from models.database import db, init_db, User
from models.api_key import APIKey
from utils.api_key_utils import generate_api_key, hash_api_key, verify_api_key
from app import create_app

# Initialize app and database
init_db()
app = create_app()

print("=== CLI AUTHENTICATION TEST ===\n")

# Get or create test user
user = User.select().first()
if not user:
    print("ERROR: No users in database!")
    sys.exit(1)

user_id = user.id
print(f"Test user ID: {user_id}\n")

# Create a new API key
print("STEP 1: Creating API key...")
api_key = generate_api_key()
print(f"  Generated key: {api_key}")

key_hash, salt = hash_api_key(api_key)
print(f"  Hash: {key_hash[:30]}...")

db_key = APIKey.create(
    user_id=user_id,
    name="CLI Auth Test",
    key_hash=key_hash,
    key_prefix=api_key[:8],
    is_active=True
)
print(f"  Stored in DB with ID: {db_key.id}\n")

# Test 1: Verify key directly
print("STEP 2: Testing verify_api_key() utility...")
try:
    verified_id = verify_api_key(api_key)
    print(f"  ✓ Verification succeeded!")
    print(f"  Returned user_id: {verified_id} (type: {type(verified_id).__name__})")
    assert verified_id == user_id
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Simulate CLI request
print("\nSTEP 3: Simulating CLI upload request...")
with app.test_client() as client:
    # Create a proper PDF file
    from io import BytesIO
    pdf_content = (
        b'%PDF-1.4\n'
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n'
        b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n'
        b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF'
    )
    
    # Make request with API key
    response = client.post(
        '/api/job/upload',
        data={'pdf': (BytesIO(pdf_content), 'test.pdf')},
        headers={'Authorization': f'ApiKey {api_key}'}
    )
    
    print(f"  Response status: {response.status_code}")
    print(f"  Response data: {response.get_json()}")
    
    if response.status_code == 202:
        print(f"  ✓ Upload succeeded!")
        job_id = response.get_json()['job_id']
        print(f"  Job ID: {job_id}")
    elif response.status_code == 401:
        print(f"  ✗ AUTHENTICATION FAILED!")
        print(f"  Error: {response.get_json()}")
        sys.exit(1)
    else:
        print(f"  ✗ Unexpected status code: {response.status_code}")
        sys.exit(1)

print("\n=== ALL TESTS PASSED ===")
