#!/usr/bin/env python3
"""Debug verify_api_key in detail."""

import sys
sys.path.insert(0, '/app')

from models.database import init_db, User
from models.api_key import APIKey
from utils.api_key_utils import generate_api_key, hash_api_key, _constant_time_compare

init_db()

print("=== VERIFY API KEY DEBUG ===\n")

# Get user
user = User.select().first()
user_id = user.id

# Generate key
api_key = generate_api_key()
print(f"Generated key: {api_key}\n")

# Hash and store
key_hash, salt = hash_api_key(api_key)
print(f"key_hash (first 50 chars): {key_hash[:50]}...")
print(f"salt: {salt}\n")

# Store in database
db_key = APIKey.create(
    user_id=user_id,
    name="Debug",
    key_hash=key_hash,
    key_prefix=api_key[:8],
    is_active=True
)
print(f"Stored in database with ID: {db_key.id}\n")

# Retrieve and check storage
retrieved_key = APIKey.get(APIKey.id == db_key.id)
print(f"Retrieved key_hash (first 50 chars): {retrieved_key.key_hash[:50]}...")
print(f"retrieved_key.is_active: {retrieved_key.is_active}\n")

# Now manually verify like verify_api_key does
print("=== MANUAL VERIFY STEPS ===\n")

# Step 1: Get prefix
key_prefix = api_key[:8]
print(f"STEP 1: Key prefix: {key_prefix}")

# Step 2: Query database
query_result = APIKey.select().where(
    (APIKey.key_prefix == key_prefix) &
    (APIKey.is_active == True)
).first()

print(f"STEP 2: Query result found: {query_result is not None}")
if query_result:
    print(f"  ID: {query_result.id}")
    print(f"  is_active: {query_result.is_active}\n")
else:
    print(f"  ERROR: Query didn't find the key!\n")
    sys.exit(1)

# Step 3: Extract stored salt
stored_salt = query_result.key_hash.split('$')[0]
print(f"STEP 3: Extracted salt: {stored_salt}")
print(f"  Matches original salt: {stored_salt == salt}\n")

# Step 4: Rehash
expected_hash, _ = hash_api_key(api_key, stored_salt)
print(f"STEP 4: Rehashed (first 50 chars): {expected_hash[:50]}...")
print(f"  Matches stored: {expected_hash == query_result.key_hash}\n")

# Step 5: Constant-time compare
cmp_result = _constant_time_compare(expected_hash, query_result.key_hash)
print(f"STEP 5: Constant-time comparison result: {cmp_result}\n")

if not cmp_result:
    print("ERROR: Constant-time comparison failed!")
    print(f"  expected_hash: {expected_hash}")
    print(f"  stored_hash:   {query_result.key_hash}")
    sys.exit(1)

# Step 6: Get user ID
user_id_result = int(query_result.user_id_id) if query_result.user_id_id else int(query_result.user_id.id)
print(f"STEP 6: User ID: {user_id_result}")

print("\n=== ALL STEPS PASSED ===")
