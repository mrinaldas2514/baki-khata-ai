"""Speech-to-text. Code outside this package only depends on the SpeechToTextClient interface."""

from fastapi import Request

from app.config import Settings, get_settings
from app.stt.base import (
    Language,
    SpeechToTextClient,
    STTNotConfiguredError,
    STTProviderError,
    Transcript,
)

__all__ = [
    "Language",
    "STTNotConfiguredError",
    "STTProviderError",
    "SpeechToTextClient",
    "Transcript",
    "build_stt_client",
    "get_stt_client",
    "stt_configured",
]


def stt_configured(settings: Settings) -> bool:
    return settings.groq_api_key is not None


def build_stt_client(settings: Settings) -> SpeechToTextClient:
    """The configured provider (Groq Whisper). Swap the implementation here to change providers."""
    if settings.groq_api_key is None:
        raise STTNotConfiguredError(
            "Voice transcription on the server is not set up: GROQ_API_KEY is missing. "
            "Add it to backend/.env (see README), or use the browser's speech recognition."
        )
    from app.stt.groq_client import GroqSTTClient

    return GroqSTTClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_stt_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def get_stt_client(request: Request) -> SpeechToTextClient:
    """FastAPI dependency. Built on first use so the rest of the API works without a key."""
    client = request.app.state.stt_client
    if client is None:
        client = build_stt_client(get_settings())
        request.app.state.stt_client = client
    return client
