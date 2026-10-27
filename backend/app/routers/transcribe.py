from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.config import get_settings
from app.schemas.transcribe import TranscribeResult, TranscribeStatus
from app.services import transcription as service
from app.stt import SpeechToTextClient, get_stt_client, stt_configured

router = APIRouter(prefix="/transcribe", tags=["voice"])
STT = Annotated[SpeechToTextClient, Depends(get_stt_client)]


@router.get("/status", response_model=TranscribeStatus)
def transcribe_status(request: Request):
    """Whether server-side transcription is set up, so the app can hide it when it isn't."""
    settings = get_settings()
    return TranscribeStatus(
        available=request.app.state.stt_client is not None or stt_configured(settings),
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
    exactly like typed text.
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
