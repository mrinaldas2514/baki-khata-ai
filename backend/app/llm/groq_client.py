import logging

import groq

from app.llm.base import ChatMessage, LLMProviderError

logger = logging.getLogger(__name__)


class GroqLLMClient:
    """LLMClient backed by Groq's chat completions API in JSON mode."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self._client = groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model

    def complete_json(self, messages: list[ChatMessage]) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                # JSON mode: the model must answer with one valid JSON object.
                response_format={"type": "json_object"},
                # Deterministic answers; the same sentence should always parse the same way.
                temperature=0,
                max_completion_tokens=300,
            )
        except groq.APIError as exc:
            logger.warning("Groq request failed: %s", exc)
            raise LLMProviderError(str(exc)) from exc
        return response.choices[0].message.content or ""
