#!/usr/bin/env python3
"""Debug API key verification flow."""

import sys
from models.database import db, init_db, User
from models.api_key import APIKey
from utils.api_key_utils import generate_api_key, hash_api_key, verify_api_key, InvalidAPIKeyError

# Initialize database
init_db()

print("=== API KEY DEBUG ===\n")

# List all API keys in database
print("STEP 1: All API keys in database:")
keys = APIKey.select()
for key in keys:
    print(f"  ID: {key.id}")
    print(f"  User ID: {key.user_id}")
    print(f"  Name: {key.name}")
    print(f"  Prefix: {key.key_prefix}")
    print(f"  Hash (first 30 chars): {key.key_hash[:30]}...")
    print(f"  Active: {key.is_active}")
    print(f"  Created: {key.created_at}")
    print()

if not keys:
    print("  (No keys found!)\n")

# Test verification with a new key
print("STEP 2: Create test key and verify:")
test_key = generate_api_key()
print(f"  Generated key: {test_key}")

hash_val, salt = hash_api_key(test_key)
print(f"  Hash: {hash_val[:30]}...")

# Get first user
user = User.select().first()
if not user:
    print("  ERROR: No users in database!")
    sys.exit(1)

user_id = user.id
print(f"  User ID: {user_id}")

# Store in database
db_key = APIKey.create(
    user_id=user_id,
    name="Debug Test Key",
    key_hash=hash_val,
    key_prefix=test_key[:8],
    is_active=True
)
print(f"  Stored in DB: {db_key.id}")

# Verify it
try:
    verified_user_id = verify_api_key(test_key)
    print(f"  ✓ Verification succeeded!")
    print(f"  Returned user_id: {verified_user_id} (type: {type(verified_user_id).__name__})")
    print(f"  Expected user_id: {user_id} (type: {type(user_id).__name__})")
    assert verified_user_id == user_id, f"Mismatch: {verified_user_id} != {user_id}"
except InvalidAPIKeyError as e:
    print(f"  ✗ Verification FAILED: {e}")
    sys.exit(1)

print("\n=== ALL CHECKS PASSED ===")
