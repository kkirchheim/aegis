"""
LLM Provider abstraction layer.

Supports multiple LLM providers (Anthropic, Ollama, etc.) with a unified interface.
"""

from .provider import LLMProvider
from .factory import get_provider

__all__ = ["LLMProvider", "get_provider"]
