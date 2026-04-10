"""
Anthropic Claude provider.

Implements LLMProvider interface using Anthropic's SDK.
"""

import os
from typing import Generator, Optional

from anthropic import Anthropic

from .provider import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Anthropic provider.

        Args:
            model: Model name (default: claude-haiku-4-5)
            api_key: API key (default: from ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        self.client = Anthropic(api_key=self.api_key)

    def complete(
        self, messages: list[dict], system: Optional[str] = None, max_tokens: int = 2048, temperature: float = 0.7
    ) -> str:
        """Get text completion from Claude."""
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}

        # Only include system if provided
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def stream(
        self, messages: list[dict], system: Optional[str] = None, max_tokens: int = 2048, temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """Stream text completion from Claude."""
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}

        # Only include system if provided
        if system:
            kwargs["system"] = system

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def get_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def get_model(self) -> str:
        """Return model name."""
        return self.model
