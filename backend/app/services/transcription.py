"""Voice input on the server: check a short recording, then hand it to the speech-to-text client.

The text that comes back goes through the same /parse -> confirmation -> /parse/confirm flow
as typed text; nothing here touches the database.
"""

from typing import BinaryIO

from app.stt import Language, SpeechToTextClient

# What browsers' MediaRecorder produces (webm: Chrome/Firefox, mp4: Safari, ogg: Firefox),
# plus common file formats, mapped to the file extension Whisper reads the format from.
AUDIO_TYPES = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
}

# Whisper adds a little padding when it measures, and recording stops a moment after the limit.
DURATION_GRACE_SECONDS = 1.5


class AudioRejectedError(Exception):
    """The upload can't be transcribed as sent (wrong type, too big, too long, empty...)."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_language(value: str | None) -> Language | None:
    """'bn-BD', 'bn-IN', 'bn' -> 'bn'; 'en-IN', 'en' -> 'en'; empty -> None (auto-detect)."""
    if value is None or not value.strip():
        return None
    code = value.strip().lower().replace("_", "-").split("-")[0]
    if code not in ("bn", "en"):
        raise AudioRejectedError(422, f"Unsupported language {value!r}. Use bn-BD, bn-IN or en-IN.")
    return code  # type: ignore[return-value]


def transcribe(
    stt: SpeechToTextClient,
    file: BinaryIO,
    content_type: str | None,
    language: str | None,
    *,
    max_bytes: int,
    max_seconds: float,
) -> str:
    lang = parse_language(language)
    mime = (content_type or "").split(";")[0].strip().lower()
    extension = AUDIO_TYPES.get(mime)
    if extension is None:
        raise AudioRejectedError(
            415, f"Unsupported audio type {mime or 'unknown'!r}. Send webm, ogg, mp4, mp3 or wav."
        )

    # Read one byte past the limit to know whether it was exceeded without reading everything.
    audio = file.read(max_bytes + 1)
    if len(audio) > max_bytes:
        raise AudioRejectedError(413, f"Recording is too large (limit {max_bytes} bytes).")
    if not audio:
        raise AudioRejectedError(422, "The recording is empty.")

    transcript = stt.transcribe(audio, f"voice.{extension}", lang)
    # The duration can only be checked after transcription: Chrome's MediaRecorder writes WebM
    # without a duration header, so the length isn't known up front. The size limit above is
    # what keeps uploads small; this keeps long recordings out of the entry box.
    seconds = transcript.duration_seconds
    if seconds is not None and seconds > max_seconds + DURATION_GRACE_SECONDS:
        raise AudioRejectedError(
            413, f"Recording is too long ({seconds:.0f} s, limit {max_seconds:.0f} s)."
        )
    return transcript.text
