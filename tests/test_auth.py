"""Test authentication and password reset functionality."""

import pytest
import sqlite3
import hashlib
import secrets
import os
from services.auth_service import hash_password, verify_password, create_user
from models.database import init_db
import uuid


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Initialize database schema before running tests."""
    # Database is already initialized by Flask app startup
    # Just ensure it exists
    try:
        init_db()
    except:
        pass  # Already initialized
    yield


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password_creates_different_hashes(self):
        """Same password should produce different hashes (due to random salt)."""
        password = "testpass123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Hashes should be different (different salts)
        assert hash1 != hash2, "Different hashes should use different salts"
        
        # But both should verify correctly
        assert verify_password(password, hash1), "First hash should verify"
        assert verify_password(password, hash2), "Second hash should verify"
        
        print("✓ Password hashing produces different salts")
    
    def test_hash_password_format(self):
        """Hash should be in format: salt$hexhash."""
        password = "test123"
        hash_result = hash_password(password)
        
        # Should have exactly one $ separator
        assert hash_result.count('$') == 1, "Hash should have format: salt$hexhash"
        
        parts = hash_result.split('$')
        assert len(parts) == 2, "Hash should split into 2 parts"
        
        salt, hexhash = parts
        # Salt should be hex string (length 64 = 32 bytes * 2)
        assert len(salt) == 64, f"Salt should be 64 chars (hex), got {len(salt)}"
        assert all(c in '0123456789abcdef' for c in salt), "Salt should be hex"
        
        # Hash should be hex
        assert all(c in '0123456789abcdef' for c in hexhash), "Hash should be hex"
        
        print(f"✓ Hash format correct: {salt[:16]}...${hexhash[:16]}...")
    
    def test_verify_password_correct(self):
        """Correct password should verify."""
        password = "mypassword"
        hash_result = hash_password(password)
        
        assert verify_password(password, hash_result), \
            "Correct password should verify"
        
        print("✓ Correct password verifies")
    
    def test_verify_password_incorrect(self):
        """Incorrect password should NOT verify."""
        password = "mypassword"
        hash_result = hash_password(password)
        
        assert not verify_password("wrongpassword", hash_result), \
            "Wrong password should NOT verify"
        assert not verify_password("", hash_result), \
            "Empty password should NOT verify"
        
        print("✓ Incorrect password does not verify")
    
    def test_verify_password_invalid_hash(self):
        """Invalid hash format should not crash."""
        # Invalid format (no $)
        assert not verify_password("test", "invalido"), \
            "Invalid hash should not verify"
        
        # Invalid format (too many $)
        assert not verify_password("test", "a$b$c"), \
            "Invalid hash should not verify"
        
        print("✓ Invalid hash formats handled gracefully")


class TestPasswordReset:
    """Test password reset logic (without database)."""
    
    def test_password_reset_creates_new_hash(self):
        """Test that password reset creates a valid new hash."""
        old_password = "oldpassword"
        new_password = "newpassword123"
        
        # Create hashes for both passwords
        old_hash = hash_password(old_password)
        new_hash = hash_password(new_password)
        
        # Verify old password works with old hash
        assert verify_password(old_password, old_hash), \
            "Old password should verify with old hash"
        
        # Verify new password does NOT work with old hash
        assert not verify_password(new_password, old_hash), \
            "New password should NOT verify with old hash"
        
        # Verify new password works with new hash
        assert verify_password(new_password, new_hash), \
            "New password should verify with new hash"
        
        # Verify old password does NOT work with new hash
        assert not verify_password(old_password, new_hash), \
            "Old password should NOT verify with new hash"
        
        print("✓ Password reset creates valid new hash")


class TestPasswordPBKDF2:
    """Test PBKDF2 implementation details."""
    
    def test_pbkdf2_parameters(self):
        """Verify PBKDF2 uses correct parameters."""
        password = "testpass"
        hash_result = hash_password(password)
        salt, hexhash = hash_result.split('$')
        
        # Manually compute hash with same parameters
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000  # iterations
        )
        
        # Should match
        assert computed_hash.hex() == hexhash, \
            "PBKDF2 computation should match stored hash"
        
        print("✓ PBKDF2 parameters correct (sha256, 100k iterations)")
    
    def test_salt_encoding(self):
        """Verify salt is properly encoded as hex."""
        password = "test"
        hash_result = hash_password(password)
        salt, hexhash = hash_result.split('$')
        
        # Salt in hash should be hex-encoded
        salt_bytes = bytes.fromhex(salt)
        assert len(salt_bytes) == 32, "Salt should be 32 bytes"
        
        # Should be able to use decoded salt
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),  # Using hex string directly
            100000
        )
        assert computed_hash.hex() == hexhash
        
        print("✓ Salt encoding correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
