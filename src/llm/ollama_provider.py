"""
Ollama provider.

Implements LLMProvider interface using Ollama's OpenAI-compatible API.
Ollama runs locally and doesn't require API keys.
"""

import os
import json
import requests
from typing import Generator, Optional
from .provider import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize Ollama provider.
        
        Args:
            model: Model name (default: llama2)
            base_url: Ollama base URL (default: http://localhost:11434)
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama2")
        self.api_url = f"{self.base_url}/api/chat"
        
        # Verify Ollama is running
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify Ollama is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ValueError(f"Ollama returned status {response.status_code}")
        except requests.RequestException as e:
            raise ValueError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running: {e}"
            )
    
    def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """Get text completion from Ollama."""
        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        # Add system message if provided
        if system:
            payload["messages"] = [
                {"role": "system", "content": system}
            ] + payload["messages"]
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=300  # 5 minute timeout for long runs
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")
    
    def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """Stream text completion from Ollama."""
        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        # Add system message if provided
        if system:
            payload["messages"] = [
                {"role": "system", "content": system}
            ] + payload["messages"]
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=300,
                stream=True
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama stream request failed: {e}")
    
    def get_name(self) -> str:
        """Return provider name."""
        return "ollama"
    
    def get_model(self) -> str:
        """Return model name."""
        return self.model
