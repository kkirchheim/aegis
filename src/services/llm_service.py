"""LLM service - LLM provider selection and initialization."""

from llm import get_provider


def init_llm_provider(app_logger=None):
    """
    Initialize LLM provider.

    Returns:
        LLM provider instance

    Raises:
        Exception: If provider initialization fails
    """
    try:
        llm_provider = get_provider()
        if app_logger:
            app_logger.info(f"✓ LLM Provider initialized: {llm_provider.get_name()} ({llm_provider.get_model()})")
        return llm_provider
    except Exception as e:
        if app_logger:
            app_logger.error(f"✗ Failed to initialize LLM provider: {e}")
        raise
