# tests/integration/test_chat_flow.py
"""Integration tests for chat API"""

import pytest
import json

pytestmark = [pytest.mark.integration, pytest.mark.api]

class TestChatSendMessage:
    """Test sending chat messages"""
    
    def test_send_message_success(self, authenticated_user, test_job):
        """Test sending a chat message"""
        response = authenticated_user.post(f'/api/job/{test_job["id"]}/chat', json={
            "message": "What are the main findings of this paper?"
        })
        
        # Should return 200 with streaming response or complete response
        assert response.status_code == 200
        # Response should contain message text
        assert len(response.data) > 0
    
    def test_send_message_empty(self, authenticated_user, test_job):
        """Test sending empty message"""
        response = authenticated_user.post(f'/api/job/{test_job["id"]}/chat', json={
            "message": ""
        })
        
        assert response.status_code == 400
    
    def test_send_message_nonexistent_job(self, authenticated_user):
        """Test sending message to non-existent job"""
        response = authenticated_user.post('/api/job/nonexistent/chat', json={
            "message": "Test"
        })
        
        assert response.status_code == 404
    
    def test_chat_requires_auth(self, client, test_job):
        """Test chat requires authentication"""
        response = client.post(f'/api/job/{test_job["id"]}/chat', json={
            "message": "Test"
        })
        
        assert response.status_code == 401

class TestChatHistory:
    """Test chat history endpoints"""
    
    def test_get_chat_history_empty(self, authenticated_user, test_job):
        """Test getting chat history when empty"""
        response = authenticated_user.get(f'/api/job/{test_job["id"]}/chat/history')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_chat_history_with_messages(self, authenticated_user, test_job_with_chat):
        """Test getting chat history with messages"""
        response = authenticated_user.get(f'/api/job/{test_job_with_chat["id"]}/chat/history')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each message should have role and content
        for msg in data:
            assert "role" in msg
            assert "content" in msg
    
    def test_history_nonexistent_job(self, authenticated_user):
        """Test getting history for non-existent job"""
        response = authenticated_user.get('/api/job/nonexistent/chat/history')
        
        assert response.status_code == 404
    
    def test_history_requires_auth(self, client, test_job):
        """Test history requires authentication"""
        response = client.get(f'/api/job/{test_job["id"]}/chat/history')
        
        assert response.status_code == 401

class TestChatClear:
    """Test clearing chat history"""
    
    def test_clear_chat_history(self, authenticated_user, test_job_with_chat):
        """Test clearing chat history"""
        # Verify history exists
        response = authenticated_user.get(f'/api/job/{test_job_with_chat["id"]}/chat/history')
        assert len(response.get_json()) > 0
        
        # Clear history
        response = authenticated_user.delete(f'/api/job/{test_job_with_chat["id"]}/chat/history')
        assert response.status_code == 204
        
        # Verify history is empty
        response = authenticated_user.get(f'/api/job/{test_job_with_chat["id"]}/chat/history')
        assert len(response.get_json()) == 0
    
    def test_clear_empty_history(self, authenticated_user, test_job):
        """Test clearing empty history"""
        response = authenticated_user.delete(f'/api/job/{test_job["id"]}/chat/history')
        
        # Should succeed even if empty
        assert response.status_code == 204
    
    def test_clear_nonexistent_job(self, authenticated_user):
        """Test clearing chat for non-existent job"""
        response = authenticated_user.delete('/api/job/nonexistent/chat/history')
        
        assert response.status_code == 404
    
    def test_clear_requires_auth(self, client, test_job):
        """Test clear requires authentication"""
        response = client.delete(f'/api/job/{test_job["id"]}/chat/history')
        
        assert response.status_code == 401

class TestChatPermissions:
    """Test chat permission boundaries"""
    
    def test_other_user_cant_access_chat(self, authenticated_user, other_user, test_job):
        """Test users can't access other users' job chats"""
        # User 1 sends message to their job
        authenticated_user.post(f'/api/job/{test_job["id"]}/chat', json={
            "message": "Test message"
        })
        
        # User 2 tries to access chat history
        response = other_user.get(f'/api/job/{test_job["id"]}/chat/history')
        
        assert response.status_code == 403
    
    def test_other_user_cant_clear_chat(self, authenticated_user, other_user, test_job):
        """Test users can't clear other users' chats"""
        response = other_user.delete(f'/api/job/{test_job["id"]}/chat/history')
        
        assert response.status_code == 403
