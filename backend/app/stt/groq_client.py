import logging

import groq

from app.groq_models import log_if_model_rejected
from app.stt.base import Language, STTProviderError, Transcript

logger = logging.getLogger(__name__)

# Whisper copies the style of the prompt, so a typical sentence nudges it towards shop words,
# digits for amounts, and (for "en") Banglish written in Latin letters instead of translating.
_PROMPTS: dict[Language | None, str] = {
    "bn": "রহিম ভাই ২ কেজি চাল ১২০ টাকা বাকি। সালমা আপা ৫০০ টাকা দিল।",
    "en": "Rahim bhai 2 kg chal 120 taka baki. Salma apa 500 taka dilo.",
    None: "Rahim bhai 2 kg chal 120 taka baki. সালমা আপা ৫০০ টাকা দিল।",
}

# Whisper's own rule for "this segment is silence": likely no speech AND a low-confidence guess.
# Without it, silence often comes back as made-up text ("Thank you.").
_NO_SPEECH_PROB = 0.6
_LOW_AVG_LOGPROB = -1.0


class GroqSTTClient:
    """SpeechToTextClient backed by Groq's Whisper transcription API."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self._client = groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model

    def transcribe(
        self, audio: bytes, filename: str, language: Language | None = None
    ) -> Transcript:
        options = {"language": language} if language else {}
        try:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=(filename, audio),
                prompt=_PROMPTS[language],
                # verbose_json adds the duration and per-segment no-speech scores.
                response_format="verbose_json",
                temperature=0,
                **options,
            )
        except groq.APIError as exc:
            log_if_model_rejected(exc, "GROQ_STT_MODEL", self._model)
            logger.warning("Groq transcription failed: %s", exc)
            raise STTProviderError(str(exc)) from exc

        segments = getattr(response, "segments", None)
        if segments:
            text = " ".join(
                _field(s, "text", "").strip() for s in segments if not _is_silence(s)
            ).strip()
        else:
            text = (response.text or "").strip()
        duration = getattr(response, "duration", None)
        return Transcript(text=text, duration_seconds=float(duration) if duration else None)


def _field(segment: object, name: str, default):
    if isinstance(segment, dict):
        return segment.get(name, default)
    return getattr(segment, name, default)


def _is_silence(segment: object) -> bool:
    return (
        _field(segment, "no_speech_prob", 0.0) > _NO_SPEECH_PROB
        and _field(segment, "avg_logprob", 0.0) < _LOW_AVG_LOGPROB
    )
