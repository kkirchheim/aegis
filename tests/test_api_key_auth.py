"""Tests for API key authentication system."""

import pytest
from datetime import datetime
from models.api_key import APIKey
from models.database import User, db
from utils.api_key_utils import (
    generate_api_key, hash_api_key, verify_api_key,
    InvalidAPIKeyError, ExpiredAPIKeyError
)


class TestAPIKeyGeneration:
    """Test API key generation."""
    
    def test_generate_api_key_format(self):
        """Generated key should have correct format."""
        key = generate_api_key()
        assert key.startswith('prc_sk_')
        assert len(key) == 39  # "prc_sk_" (7) + 32 random chars
    
    def test_generate_api_key_uniqueness(self):
        """Each generated key should be unique."""
        keys = [generate_api_key() for _ in range(10)]
        assert len(set(keys)) == 10  # All unique


class TestAPIKeyHashing:
    """Test API key hashing and verification."""
    
    def test_hash_api_key_returns_tuple(self):
        """hash_api_key should return (hash, salt) tuple."""
        key = generate_api_key()
        result = hash_api_key(key)
        assert isinstance(result, tuple)
        assert len(result) == 2
        hash_val, salt = result
        assert isinstance(hash_val, str)
        assert isinstance(salt, str)
        assert '$' in hash_val  # Format: salt$hash
    
    def test_hash_api_key_with_salt(self):
        """hash_api_key with provided salt should work."""
        key = generate_api_key()
        salt = "test_salt_hex"
        hash_val, returned_salt = hash_api_key(key, salt)
        assert returned_salt == salt
        assert '$' in hash_val
    
    def test_hash_api_key_consistency(self):
        """Same key + salt should produce same hash."""
        key = generate_api_key()
        salt = "test_salt"
        hash1, _ = hash_api_key(key, salt)
        hash2, _ = hash_api_key(key, salt)
        assert hash1 == hash2
    
    def test_hash_api_key_different_salts(self):
        """Different salts should produce different hashes."""
        key = generate_api_key()
        hash1, salt1 = hash_api_key(key)
        hash2, salt2 = hash_api_key(key)
        assert hash1 != hash2
        assert salt1 != salt2


class TestAPIKeyStorage:
    """Test API key storage and retrieval."""
    
    def test_create_api_key_in_database(self, authenticated_user):
        """API key should be storable in database."""
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        db_key = APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        
        assert db_key.id is not None
        assert db_key.user_id_id == user_id
        assert db_key.name == "Test Key"
        assert db_key.key_hash == key_hash
        assert db_key.key_prefix == key_prefix
        assert db_key.is_active is True
    
    def test_retrieve_api_key_by_prefix(self, authenticated_user):
        """API key should be retrievable by prefix."""
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        
        # Retrieve by prefix
        db_key = APIKey.select().where(
            (APIKey.key_prefix == key_prefix) &
            (APIKey.is_active == True)
        ).first()
        
        assert db_key is not None
        assert db_key.key_prefix == key_prefix


class TestAPIKeyVerification:
    """Test API key verification logic."""
    
    def test_verify_valid_api_key(self, authenticated_user):
        """Valid API key should verify successfully."""
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        # Store in database
        APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        
        # Verify the key
        result_user_id = verify_api_key(api_key)
        assert result_user_id == user_id
    
    def test_verify_invalid_api_key_format(self):
        """Invalid format key should raise error."""
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key("invalid_key")
    
    def test_verify_nonexistent_api_key(self):
        """Non-existent key should raise error."""
        api_key = generate_api_key()
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(api_key)
    
    def test_verify_inactive_api_key(self, authenticated_user):
        """Inactive key should not verify."""
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        # Create inactive key
        APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix,
            is_active=False
        )
        
        # Should not verify
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(api_key)
    
    def test_verify_expired_api_key(self, authenticated_user):
        """Expired key should not verify."""
        from datetime import datetime, timedelta
        
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        # Create expired key
        APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        # Should raise ExpiredAPIKeyError
        with pytest.raises(ExpiredAPIKeyError):
            verify_api_key(api_key)
    
    def test_verify_updates_last_used(self, authenticated_user):
        """Verification should update last_used_at timestamp."""
        with authenticated_user.session_transaction() as sess:
            user_id = sess['user_id']
        api_key = generate_api_key()
        key_hash, _ = hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        db_key = APIKey.create(
            user_id=user_id,
            name="Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        
        assert db_key.last_used_at is None
        
        # Verify key
        verify_api_key(api_key)
        
        # Reload and check
        db_key = APIKey.get_by_id(db_key.id)
        assert db_key.last_used_at is not None


class TestAPIKeyEndpoints:
    """Test API key management endpoints."""
    
    def test_create_api_key_via_endpoint(self, authenticated_user):
        """POST /api/keys should create key and return it."""
        response = authenticated_user.post('/api/keys', json={
            'name': 'CLI Tool'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        
        # Check response format
        assert 'key' in data
        assert 'id' in data
        assert 'name' in data
        assert 'key_prefix' in data
        assert 'created_at' in data
        
        # Verify key format
        assert data['key'].startswith('prc_sk_')
        assert data['key_prefix'] == data['key'][:8]
        assert data['name'] == 'CLI Tool'
    
    def test_list_api_keys_via_endpoint(self, authenticated_user):
        """GET /api/keys should list all keys."""
        # Create two keys
        key1_response = authenticated_user.post('/api/keys', json={'name': 'Key 1'})
        key2_response = authenticated_user.post('/api/keys', json={'name': 'Key 2'})
        
        assert key1_response.status_code == 201
        assert key2_response.status_code == 201
        
        # List keys
        response = authenticated_user.get('/api/keys')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'keys' in data
        assert 'total' in data
        
        # Should have at least 2 keys
        assert data['total'] >= 2
        assert len(data['keys']) >= 2
        
        # Keys should have prefix only, not full key
        for key in data['keys']:
            assert 'key_prefix' in key
            assert 'key' not in key  # Full key never shown
            assert key['key_prefix'].startswith('prc_sk_')
    
    def test_delete_api_key_via_endpoint(self, authenticated_user):
        """DELETE /api/keys/{key_id} should revoke key."""
        # Create key
        create_response = authenticated_user.post('/api/keys', json={'name': 'Temp Key'})
        key_id = create_response.get_json()['id']
        
        # Delete key
        delete_response = authenticated_user.delete(f'/api/keys/{key_id}')
        assert delete_response.status_code == 204
        
        # Verify key is gone
        list_response = authenticated_user.get('/api/keys')
        keys = list_response.get_json()['keys']
        key_ids = [k['id'] for k in keys]
        assert key_id not in key_ids
    
    def test_delete_nonexistent_api_key(self, authenticated_user):
        """DELETE on non-existent key should return 404."""
        response = authenticated_user.delete('/api/keys/fake-id-12345')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data


class TestAPIKeyAuthentication:
    """Test using API keys to authenticate API requests."""
    
    def test_authenticate_with_api_key(self, authenticated_user, client):
        """Should be able to authenticate to /api/keys using generated key."""
        # Create key
        create_response = authenticated_user.post('/api/keys', json={'name': 'Auth Test'})
        api_key = create_response.get_json()['key']

        # Try to list keys using API key (client has no session)
        response = client.get(
            '/api/keys',
            headers={'Authorization': f'ApiKey {api_key}'}
        )

        # Should succeed
        assert response.status_code == 200
        data = response.get_json()
        assert 'keys' in data

    def test_reject_invalid_api_key_header(self, client):
        """Invalid API key in header should return 401."""
        response = client.get(
            '/api/keys',
            headers={'Authorization': 'ApiKey invalid_key_12345'}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_reject_missing_authorization_header(self, client):
        """Missing Authorization header should return 401."""
        response = client.get('/api/keys')

        # Without session cookie or API key, should fail
        assert response.status_code == 401
    
    def test_authenticate_with_cookie_and_api_key(self, authenticated_user, client):
        """Should accept both cookie and API key authentication."""
        # Create key
        create_response = authenticated_user.post('/api/keys', json={'name': 'Dual Auth'})
        api_key = create_response.get_json()['key']
        
        # Both should work
        # 1. With cookie (authenticated_user has session)
        cookie_response = authenticated_user.get('/api/keys')
        assert cookie_response.status_code == 200
        
        # 2. With API key (new client)
        key_response = client.get(
            '/api/keys',
            headers={'Authorization': f'ApiKey {api_key}'}
        )
        assert key_response.status_code == 200
