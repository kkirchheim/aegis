"""
Abstract base class for LLM providers.

Each provider implements a common interface for:
- Text completion
- Streaming responses
- Configuration
"""

from abc import ABC, abstractmethod
from typing import Generator, Optional


class Message:
    """Represents a message in a conversation."""
    def __init__(self, role: str, content: str):
        self.role = role  # "user", "assistant", "system"
        self.content = content
    
    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """
        Get a text completion from the model.
        
        Args:
            messages: List of dicts with 'role' and 'content' keys
            system: System prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
        
        Returns:
            str: Model's text response
        """
        pass
    
    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """
        Stream a text completion from the model.
        
        Args:
            messages: List of dicts with 'role' and 'content' keys
            system: System prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
        
        Yields:
            str: Chunks of the model's response
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return provider name (e.g., 'anthropic', 'ollama')."""
        pass
    
    @abstractmethod
    def get_model(self) -> str:
        """Return current model name."""
        pass
