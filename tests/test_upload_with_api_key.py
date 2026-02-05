"""Test that upload endpoint accepts API key authentication."""

import pytest
import os
from io import BytesIO
from pathlib import Path


class TestUploadWithAPIKey:
    """Test POST /api/job/upload with API key authentication."""
    
    def test_upload_with_api_key(self, authenticated_user, client):
        """
        Main test: Upload PDF using API key (not session cookie).
        This is the flow the CLI uses.
        """
        # Step 1: Create API key (via authenticated session)
        create_response = authenticated_user.post('/api/keys', json={'name': 'CLI Upload Test'})
        assert create_response.status_code == 201
        api_key = create_response.get_json()['key']
        print(f"\n✓ Created API key: {api_key[:20]}...\n")
        
        # Step 2: Create a dummy PDF file
        # Find the test fixtures directory
        test_dir = Path(__file__).parent
        fixtures_dir = test_dir / 'fixtures'
        fixtures_dir.mkdir(exist_ok=True)
        
        # Create minimal PDF content
        pdf_path = fixtures_dir / 'test_upload.pdf'
        with open(pdf_path, 'wb') as f:
            # Minimal PDF structure
            f.write(b'%PDF-1.4\n')
            f.write(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
            f.write(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
            f.write(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n')
            f.write(b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n')
            f.write(b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF')
        
        # Step 3: Upload using API key (no session cookie)
        print("Uploading PDF with API key authentication...")
        with open(pdf_path, 'rb') as f:
            response = client.post(
                '/api/job/upload',
                data={'pdf': f},
                headers={'Authorization': f'ApiKey {api_key}'}
            )
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.get_json()}")
        
        # Step 4: Verify success (202 Accepted, not 401 Unauthorized)
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.get_json()}"
        
        data = response.get_json()
        assert 'job_id' in data
        assert data['status'] == 'pending'
        assert 'Paper uploaded' in data['message']
        
        print(f"✓ Upload successful! Job ID: {data['job_id']}\n")
        
        # Cleanup
        pdf_path.unlink()
    
    def test_upload_with_invalid_api_key(self, client):
        """Invalid API key should return 401."""
        # Create dummy PDF
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< >>\nendobj\nxref\ntrailer\n<< >>\n%%EOF'
        
        response = client.post(
            '/api/job/upload',
            data={'pdf': (BytesIO(pdf_content), 'test.pdf')},
            headers={'Authorization': 'ApiKey invalid_key_12345'}
        )
        
        assert response.status_code == 401
        assert 'error' in response.get_json()
    
    def test_upload_without_auth(self, client):
        """No authentication should return 401."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< >>\nendobj\nxref\ntrailer\n<< >>\n%%EOF'
        
        response = client.post(
            '/api/job/upload',
            data={'pdf': (BytesIO(pdf_content), 'test.pdf')}
        )
        
        assert response.status_code == 401
        assert 'error' in response.get_json()
    
    def test_upload_with_session_still_works(self, authenticated_user):
        """Verify that session cookie auth still works (backward compatibility)."""
        # Create dummy PDF
        test_dir = Path(__file__).parent
        fixtures_dir = test_dir / 'fixtures'
        fixtures_dir.mkdir(exist_ok=True)
        
        pdf_path = fixtures_dir / 'test_upload_session.pdf'
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n')
            f.write(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
            f.write(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
            f.write(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n')
            f.write(b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n')
            f.write(b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF')
        
        # Upload with session (no API key)
        with open(pdf_path, 'rb') as f:
            response = authenticated_user.post(
                '/api/job/upload',
                data={'pdf': f}
            )
        
        # Should succeed (202, not 401)
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.get_json()}"
        assert 'job_id' in response.get_json()
        
        # Cleanup
        pdf_path.unlink()
