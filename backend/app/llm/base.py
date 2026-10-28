"""The small interface every LLM provider implements, so the provider can be swapped later."""

from typing import Literal, Protocol, TypedDict

# Which kind of parser read a sentence: a language model, or the simple rules (AI off / no key).
ParserKind = Literal["llm", "rules"]


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(Protocol):
    # Shown with every parse result ("AI" / "AI chhara" on the confirmation card).
    parser: ParserKind
    # The provider's model id, e.g. "openai/gpt-oss-120b" ("rule-based" for the rules).
    model: str

    def complete_json(self, messages: list[ChatMessage]) -> str:
        """Send a chat and return the model's reply, which should be a single JSON object.

        Raises LLMProviderError if the provider can't be reached or refuses the request.
        """
        ...


class LLMNotConfiguredError(Exception):
    """No API key (or other required setting) for the LLM provider."""


class LLMProviderError(Exception):
    """The provider failed: network error, timeout, bad key, rate limit, server error."""
