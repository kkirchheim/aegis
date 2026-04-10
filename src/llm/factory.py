"""
LLM Provider factory.

Creates provider instances based on configuration.
"""

import os
from typing import Optional
from .provider import LLMProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Get an LLM provider instance.
    
    Args:
        provider_name: Provider name ('anthropic' or 'ollama').
                      If None, uses LLM_PROVIDER env var (default: 'anthropic')
    
    Returns:
        LLMProvider instance
    
    Raises:
        ValueError: If provider not found or configuration invalid
    """
    provider_name = provider_name or os.getenv("LLM_PROVIDER", "anthropic")
    provider_name = provider_name.lower().strip()
    
    if provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Supported: 'anthropic', 'ollama'"
        )
