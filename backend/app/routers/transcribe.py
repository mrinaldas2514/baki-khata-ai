from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.auth import CurrentUser
from app.config import get_settings
from app.rate_limit import check_rate
from app.schemas.transcribe import TranscribeResult, TranscribeStatus
from app.services import transcription as service
from app.stt import SpeechToTextClient, get_stt_client, stt_configured

router = APIRouter(prefix="/transcribe", tags=["voice"])


class AIDisabledError(Exception):
    """The shopkeeper turned AI off, so nothing may be sent to the AI provider (403)."""


def _stt_if_allowed(request: Request, user: CurrentUser) -> SpeechToTextClient:
    if not user.ai_enabled:
        raise AIDisabledError(
            "AI is turned off in the settings, so voice is not sent to the server. "
            "Use the browser's voice input or type."
        )
    check_rate(request, "transcribe", f"shop:{user.shop_id}")
    return get_stt_client(request)


STT = Annotated[SpeechToTextClient, Depends(_stt_if_allowed)]


@router.get("/status", response_model=TranscribeStatus)
def transcribe_status(request: Request, user: CurrentUser):
    """Whether server-side transcription can be used, so the app can hide it when it can't.

    False without a key, and when the shopkeeper turned AI off.
    """
    settings = get_settings()
    configured = request.app.state.stt_client is not None or stt_configured(settings)
    return TranscribeStatus(
        available=configured and user.ai_enabled,
        max_seconds=settings.stt_max_audio_seconds,
        max_bytes=settings.stt_max_audio_bytes,
    )


@router.post("", response_model=TranscribeResult)
def transcribe_audio(
    stt: STT,
    file: Annotated[UploadFile, File(description="A short recording (webm, ogg, mp4, mp3, wav)")],
    language: Annotated[
        str | None, Form(description="bn-BD, bn-IN or en-IN. Leave out to auto-detect.")
    ] = None,
):
    """Turn a short recording into text for the entry box. Saves nothing.

    The text is meant to be checked by the shopkeeper and then sent to /shops/{id}/parse,
    exactly like typed text. Only used when the browser can't do speech recognition itself
    (or the shopkeeper prefers the server); 403 when AI is turned off.
    """
    settings = get_settings()
    text = service.transcribe(
        stt,
        file.file,
        file.content_type,
        language,
        max_bytes=settings.stt_max_audio_bytes,
        max_seconds=settings.stt_max_audio_seconds,
    )
    return TranscribeResult(text=text)
