"""Chat service - interactive Q&A about analyzed papers."""

import threading
from typing import List, Dict, Optional, Callable
from repositories import ChatRepository, JobRepository
from database import get_db


class ChatService:
    """Service for paper analysis chat interactions."""
    
    @staticmethod
    def get_or_create_session(job_id: str) -> int:
        """Get or create chat session. Returns session_id."""
        return ChatRepository.get_or_create_session(job_id)
    
    @staticmethod
    def save_message(session_id: int, role: str, content: str) -> bool:
        """Store chat message. Returns True on success."""
        return ChatRepository.save_message(session_id, role, content)
    
    @staticmethod
    def get_history(session_id: int, limit: int = 20) -> List[Dict]:
        """Get chat history. Returns list of messages in chronological order."""
        messages = ChatRepository.get_history(session_id, limit=limit)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
            }
            for msg in messages
        ]
    
    @staticmethod
    def clear_history(session_id: int) -> bool:
        """Delete all messages in session. Returns True on success."""
        return ChatRepository.clear_history(session_id)
    
    @staticmethod
    def verify_access(job_id: str, user_id: int) -> tuple[bool, Optional[str]]:
        """Verify user owns job. Returns (ok, error_message)."""
        job = JobRepository.get(job_id)
        
        if not job:
            return False, "Job not found"
        
        if job.user_id != user_id:
            return False, "Access denied"
        
        if job.status not in ["completed", "processing"]:
            return False, "Job analysis not complete"
        
        return True, None
    
    @staticmethod
    def generate_response_background(
        job_id: str,
        session_id: int,
        messages: List[Dict],
        llm_provider,
        emit_event: Callable,
    ):
        """Generate chat response in background thread with streaming."""
        try:
            full_response = ""
            
            # Stream response from LLM
            for chunk in llm_provider.stream(
                messages=messages,
                max_tokens=2048,
                temperature=0.7
            ):
                if not chunk:
                    continue
                
                full_response += chunk
                
                # Emit chunk for real-time streaming
                emit_event(job_id, {
                    "step": "chat_response",
                    "content": chunk
                })
            
            # Verify we got a response
            if not full_response:
                emit_event(job_id, {
                    "step": "chat_error",
                    "message": "Error: Empty response from LLM"
                })
                return
            
            # Store complete response in DB
            ChatService.save_message(session_id, "assistant", full_response)
            
            # Signal completion
            emit_event(job_id, {
                "step": "chat_complete",
                "message": "Response complete"
            })
        
        except Exception as e:
            emit_event(job_id, {
                "step": "chat_error",
                "message": f"Error: {str(e)}"
            })
    
    @staticmethod
    def start_response_thread(
        job_id: str,
        session_id: int,
        messages: List[Dict],
        llm_provider,
        emit_event: Callable,
    ) -> bool:
        """Start background thread to generate response. Returns True on success."""
        try:
            thread = threading.Thread(
                target=ChatService.generate_response_background,
                args=(job_id, session_id, messages, llm_provider, emit_event),
                daemon=True
            )
            thread.start()
            return True
        except Exception:
            return False
