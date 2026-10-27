"""LLM access. Code outside this package only depends on the LLMClient interface."""

import logging

from fastapi import Request

from app.config import Settings, get_settings
from app.llm.base import ChatMessage, LLMClient, LLMNotConfiguredError, LLMProviderError

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMNotConfiguredError",
    "LLMProviderError",
    "build_llm_client",
    "get_llm_client",
]

logger = logging.getLogger(__name__)


def build_llm_client(settings: Settings) -> LLMClient:
    """The configured provider (LLM_PROVIDER). Swap the implementation here to change providers."""
    provider = settings.llm_provider
    if provider == "auto":
        provider = "groq" if settings.groq_api_key is not None else "fake"
    if provider == "fake":
        from app.llm.rule_based import RuleBasedLLMClient

        logger.warning(
            "AI parsing uses the simple rule-based demo parser (LLM_PROVIDER=fake or no "
            "GROQ_API_KEY). Set GROQ_API_KEY for real AI parsing."
        )
        return RuleBasedLLMClient()

    if settings.groq_api_key is None:
        raise LLMNotConfiguredError(
            "AI parsing is not set up: GROQ_API_KEY is missing. "
            "Add it to backend/.env (see README) or enter the transaction manually."
        )
    from app.llm.groq_client import GroqLLMClient

    return GroqLLMClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def get_llm_client(request: Request) -> LLMClient:
    """FastAPI dependency. Built on first use so the rest of the API works without a key."""
    client = request.app.state.llm_client
    if client is None:
        client = build_llm_client(get_settings())
        request.app.state.llm_client = client
    return client
