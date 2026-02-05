#!/usr/bin/env python3
"""Debug hash generation and verification."""

import sys
sys.path.insert(0, '/app')

from utils.api_key_utils import generate_api_key, hash_api_key

print("=== HASH DEBUG ===\n")

# Test 1: Generate key and hash
key = generate_api_key()
print(f"Generated key: {key}")

hash1, salt1 = hash_api_key(key)
print(f"Hash 1: {hash1[:50]}...")
print(f"Salt 1: {salt1}\n")

# Test 2: Rehash with the same salt
hash2, salt2 = hash_api_key(key, salt1)
print(f"Hash 2: {hash2[:50]}...")
print(f"Salt 2: {salt2}\n")

# Test 3: Compare them
print("Comparing hashes:")
print(f"  hash1 == hash2: {hash1 == hash2}")
print(f"  salt1 == salt2: {salt1 == salt2}\n")

if hash1 != hash2:
    print("ERROR: Hashes don't match!")
    print(f"  hash1: {hash1}")
    print(f"  hash2: {hash2}")
    sys.exit(1)

# Test 4: Extract salt and rehash like verify_api_key does
print("Simulating verify_api_key logic:")
stored_hash = hash1
stored_salt = stored_hash.split('$')[0]
print(f"Stored hash (first 50 chars): {stored_hash[:50]}...")
print(f"Extracted salt: {stored_salt}")

rehashed, _ = hash_api_key(key, stored_salt)
print(f"Rehashed (first 50 chars): {rehashed[:50]}...")

print(f"\nstored_hash == rehashed: {stored_hash == rehashed}")

if stored_hash != rehashed:
    print("ERROR: Stored hash doesn't match rehashed!")
    print(f"  stored_hash: {stored_hash}")
    print(f"  rehashed:    {rehashed}")
    sys.exit(1)

print("\n=== ALL HASH TESTS PASSED ===")
