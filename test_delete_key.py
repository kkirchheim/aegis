#!/usr/bin/env python3
"""Test API key deletion endpoint."""

import sys
sys.path.insert(0, '/app')

from models.database import init_db, User
from models.api_key import APIKey
from utils.api_key_utils import generate_api_key, hash_api_key
from app import create_app

init_db()
app = create_app()

print("=== DELETE ENDPOINT TEST ===\n")

user = User.select().first()
user_id = user.id

# Create a test key
api_key = generate_api_key()
key_hash, _ = hash_api_key(api_key)

db_key = APIKey.create(
    user_id=user_id,
    name="Test Delete Key",
    key_hash=key_hash,
    key_prefix=api_key[:8],
    is_active=True
)
key_id = db_key.id
print(f"Created key with ID: {key_id}\n")

# Verify it exists
assert APIKey.get_or_none(APIKey.id == key_id) is not None
print(f"✓ Key exists in database\n")

# Test deletion via endpoint
print("Testing DELETE /api/keys/{key_id}...")
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    
    response = client.delete(
        f'/api/keys/{key_id}'
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.data}")
    
    if response.status_code == 204:
        print("✓ Delete returned 204 (No Content)")
    else:
        print(f"✗ Expected 204, got {response.status_code}")
        sys.exit(1)

# Verify it's gone
deleted_key = APIKey.get_or_none(APIKey.id == key_id)
if deleted_key is None:
    print("✓ Key deleted from database")
else:
    print(f"✗ Key still exists in database: is_active={deleted_key.is_active}")
    sys.exit(1)

print("\n=== DELETE TEST PASSED ===")
