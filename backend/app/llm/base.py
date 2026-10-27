"""The small interface every LLM provider implements, so the provider can be swapped later."""

from typing import Literal, Protocol, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(Protocol):
    def complete_json(self, messages: list[ChatMessage]) -> str:
        """Send a chat and return the model's reply, which should be a single JSON object.

        Raises LLMProviderError if the provider can't be reached or refuses the request.
        """
        ...


class LLMNotConfiguredError(Exception):
    """No API key (or other required setting) for the LLM provider."""


class LLMProviderError(Exception):
    """The provider failed: network error, timeout, bad key, rate limit, server error."""
