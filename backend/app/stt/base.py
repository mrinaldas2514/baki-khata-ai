"""The small interface every speech-to-text provider implements, so it can be swapped later."""

from dataclasses import dataclass
from typing import Literal, Protocol

# Languages the app lets the shopkeeper pick (ISO 639-1, what Whisper expects).
Language = Literal["bn", "en"]


@dataclass(frozen=True)
class Transcript:
    text: str
    # Length of the audio as the provider measured it, if it reports one.
    duration_seconds: float | None = None


class SpeechToTextClient(Protocol):
    def transcribe(
        self, audio: bytes, filename: str, language: Language | None = None
    ) -> Transcript:
        """Turn a short recording into text. `filename`'s extension tells the format (.webm...).

        Returns an empty text when nobody spoke. Raises STTProviderError if the provider
        can't be reached or refuses the request.
        """
        ...


class STTNotConfiguredError(Exception):
    """No API key (or other required setting) for the speech-to-text provider."""


class STTProviderError(Exception):
    """The provider failed: network error, timeout, bad key, rate limit, unreadable audio."""
