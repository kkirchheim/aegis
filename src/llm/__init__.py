"""
LLM Provider abstraction layer.

Supports multiple LLM providers (Anthropic, Ollama, etc.) with a unified interface.
"""

from .factory import get_provider
from .provider import LLMProvider

__all__ = ["LLMProvider", "get_provider"]
