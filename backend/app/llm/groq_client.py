import logging

import groq

from app.groq_models import log_if_model_rejected
from app.llm.base import ChatMessage, LLMProviderError

logger = logging.getLogger(__name__)

# Reasoning models think before answering, and those tokens count towards the answer's limit.
# Low effort is plenty for one short sentence and keeps parsing fast.
_REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)


class GroqLLMClient:
    """LLMClient backed by Groq's chat completions API in JSON mode."""

    parser = "llm"

    def __init__(
        self, api_key: str, model: str, timeout_seconds: float = 20.0, max_retries: int = 1
    ) -> None:
        # The SDK waits as long as Groq's Retry-After says before retrying a 429.
        self._client = groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        self._model = model
        self._reasoning = model.startswith(_REASONING_MODEL_PREFIXES)

    @property
    def model(self) -> str:
        return self._model

    def complete_json(self, messages: list[ChatMessage]) -> str:
        options = {"reasoning_effort": "low"} if self._reasoning else {}
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                # JSON mode: the model must answer with one valid JSON object.
                response_format={"type": "json_object"},
                # Deterministic answers; the same sentence should always parse the same way.
                temperature=0,
                max_completion_tokens=1024 if self._reasoning else 400,
                **options,
            )
        except groq.APIError as exc:
            log_if_model_rejected(exc, "GROQ_MODEL", self._model)
            logger.warning("Groq request failed: %s", exc)
            raise LLMProviderError(str(exc)) from exc
        return response.choices[0].message.content or ""
