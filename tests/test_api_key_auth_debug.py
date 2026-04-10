"""Debug tests for API key authentication - focused on the 401 issue."""

from models.api_key import APIKey
from utils.api_key_utils import ExpiredAPIKeyError, InvalidAPIKeyError, generate_api_key, hash_api_key, verify_api_key


class TestAPIKeyDebug:
    """Debug the 401 authentication failure."""

    def test_end_to_end_api_key_flow(self, authenticated_user, client):
        """
        Reproduce the exact flow:
        1. User creates API key via UI endpoint
        2. Immediately use that key to auth to /api/keys
        3. Should succeed (not 401)
        """
        print("\n\n=== DEBUGGING API KEY AUTH ===\n")

        # Step 1: Create key via endpoint (like UI does)
        print("STEP 1: Creating API key via POST /api/keys")
        create_response = authenticated_user.post("/api/keys", json={"name": "Debug Key"})
        print(f"  Status: {create_response.status_code}")
        assert create_response.status_code == 201, f"Failed to create key: {create_response.data}"

        data = create_response.get_json()
        api_key = data["key"]
        key_id = data["id"]
        print(f"  Key created: {api_key[:20]}...")
        print(f"  Key ID: {key_id}")
        print(f"  Key prefix: {data['key_prefix']}")

        # Step 2: Query the database to verify it was stored
        print("\nSTEP 2: Checking database storage")
        db_key = APIKey.get_or_none(APIKey.id == key_id)
        assert db_key is not None, "Key not found in database!"
        print(f"  Key found in DB: {db_key.key_prefix}")
        print(f"  Key hash (first 20 chars): {db_key.key_hash[:20]}...")
        print(f"  Is active: {db_key.is_active}")

        # Step 3: Test verify_api_key utility directly
        print("\nSTEP 3: Testing verify_api_key() utility function")
        try:
            verified_user_id = verify_api_key(api_key)
            print("  ✓ verify_api_key() succeeded!")
            print(f"  Returned user_id: {verified_user_id}")
            with authenticated_user.session_transaction() as sess:
                expected_user_id = sess["user_id"]
            print(f"  Expected user_id: {expected_user_id}")
            assert verified_user_id == expected_user_id
        except (InvalidAPIKeyError, ExpiredAPIKeyError) as e:
            print(f"  ✗ verify_api_key() FAILED: {e}")
            raise

        # Step 4: Test the API endpoint with Authorization header
        print("\nSTEP 4: Testing API endpoint with Authorization header")
        print(f"  Header: Authorization: ApiKey {api_key[:20]}...")

        response = client.get("/api/keys", headers={"Authorization": f"ApiKey {api_key}"})

        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.get_json()}")

        # This is where the user gets 401
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.get_json()}"

    def test_api_key_verification_hash_matching(self):
        """Debug hash matching - verify constant_time_compare works."""
        print("\n\n=== DEBUGGING HASH MATCHING ===\n")

        key = generate_api_key()
        print(f"Generated key: {key}")

        # Hash it once
        hash1, salt = hash_api_key(key)
        print(f"Hash 1: {hash1[:30]}...")
        print(f"Salt: {salt}")

        # Hash again with same salt
        hash2, _ = hash_api_key(key, salt)
        print(f"Hash 2: {hash2[:30]}...")

        # They should match
        assert hash1 == hash2, "Hashes don't match with same salt!"
        print("✓ Hashes match")

        # Now test the constant-time comparison
        from utils.api_key_utils import _constant_time_compare

        result = _constant_time_compare(hash1, hash2)
        print(f"Constant-time compare result: {result}")
        assert result is True, "Constant-time compare failed!"
        print("✓ Constant-time comparison works")

    def test_api_key_prefix_query(self, app):
        """Debug prefix querying from database."""
        print("\n\n=== DEBUGGING PREFIX QUERY ===\n")

        key = generate_api_key()
        prefix = key[:8]
        print(f"Generated key: {key}")
        print(f"Prefix: {prefix}")

        # Count how many keys have this prefix (should be 0 initially)
        count = APIKey.select().where(APIKey.key_prefix == prefix).count()
        print(f"Keys with this prefix in DB: {count}")

        if count > 0:
            print("⚠️  Warning: This prefix already exists in the database!")
            existing = APIKey.get(APIKey.key_prefix == prefix)
            print(f"  Existing key: active={existing.is_active}, user_id={existing.user_id}")
