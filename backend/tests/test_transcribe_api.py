"""POST /transcribe (voice recording -> text for the entry box) and GET /transcribe/status."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.stt import STTProviderError, Transcript
from tests.conftest import FakeSTT, error_messages

AUDIO = b"\x1aE\xdf\xa3 fake webm bytes"


def upload(client, audio=AUDIO, content_type="audio/webm;codecs=opus", **form):
    return client.post(
        "/transcribe", files={"file": ("voice.webm", audio, content_type)}, data=form
    )


@pytest.fixture
def settings(monkeypatch) -> Settings:
    settings = Settings(_env_file=None, stt_max_audio_bytes=1000, stt_max_audio_seconds=30)
    monkeypatch.setattr("app.routers.transcribe.get_settings", lambda: settings)
    return settings


def test_returns_the_transcript(client, fake_stt: FakeSTT):
    fake_stt.reply(Transcript(text="rahim bhai 2 kg chal 120 taka baki", duration_seconds=3.2))

    response = upload(client, language="en-IN")

    assert response.status_code == 200, response.text
    assert response.json() == {"text": "rahim bhai 2 kg chal 120 taka baki"}
    assert fake_stt.calls == [{"audio": AUDIO, "filename": "voice.webm", "language": "en"}]


@pytest.mark.parametrize(
    ("language", "expected"),
    [("bn-BD", "bn"), ("bn-IN", "bn"), ("bn", "bn"), ("EN_in", "en"), ("", None), (None, None)],
)
def test_language_is_reduced_to_the_whisper_code(client, fake_stt: FakeSTT, language, expected):
    fake_stt.reply("রহিম ১২০ টাকা বাকি")
    form = {} if language is None else {"language": language}
    assert upload(client, **form).status_code == 200
    assert fake_stt.calls[0]["language"] == expected


@pytest.mark.parametrize(
    ("content_type", "filename"),
    [
        ("audio/mp4", "voice.mp4"),
        ("audio/ogg;codecs=opus", "voice.ogg"),
        ("audio/wav", "voice.wav"),
    ],
)
def test_filename_extension_follows_the_audio_type(
    client, fake_stt: FakeSTT, content_type, filename
):
    fake_stt.reply("salma 500 dilo")
    assert upload(client, content_type=content_type).status_code == 200
    assert fake_stt.calls[0]["filename"] == filename


def test_no_speech_returns_empty_text(client, fake_stt: FakeSTT):
    fake_stt.reply(Transcript(text="", duration_seconds=2.0))
    response = upload(client)
    assert response.status_code == 200
    assert response.json() == {"text": ""}


def test_rejects_unsupported_language(client, fake_stt: FakeSTT):
    response = upload(client, language="hi-IN")
    assert response.status_code == 422
    assert "Unsupported language" in response.json()["detail"]
    assert fake_stt.calls == []


@pytest.mark.parametrize("content_type", ["text/plain", "image/png", "application/octet-stream"])
def test_rejects_non_audio(client, fake_stt: FakeSTT, content_type):
    response = upload(client, content_type=content_type)
    assert response.status_code == 415
    assert fake_stt.calls == []


def test_rejects_empty_recording(client, fake_stt: FakeSTT):
    response = upload(client, audio=b"")
    assert response.status_code == 422
    assert response.json()["detail"] == "The recording is empty."
    assert fake_stt.calls == []


def test_missing_file_is_a_field_error(client, fake_stt: FakeSTT):
    response = client.post("/transcribe", data={"language": "bn-BD"})
    assert response.status_code == 422
    assert "file" in error_messages(response)
    assert fake_stt.calls == []


def test_rejects_too_large_recording(client, fake_stt: FakeSTT, settings):
    fake_stt.reply("ok")
    assert upload(client, audio=b"x" * 1000).status_code == 200
    response = upload(client, audio=b"x" * 1001)
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]
    assert len(fake_stt.calls) == 1  # only the one at the limit was sent


def test_rejects_too_long_recording(client, fake_stt: FakeSTT, settings):
    fake_stt.reply(
        Transcript(text="just under", duration_seconds=31.0),
        Transcript(text="a long story", duration_seconds=45.0),
    )
    assert upload(client).status_code == 200  # within the grace period
    response = upload(client)
    assert response.status_code == 413
    assert "too long" in response.json()["detail"]


def test_provider_failure_is_502_without_details(client, fake_stt: FakeSTT, caplog):
    fake_stt.reply(STTProviderError("invalid api key gsk_secret"))
    response = upload(client)
    assert response.status_code == 502
    assert "gsk_secret" not in response.text
    assert "gsk_secret" in caplog.text


def test_status_reports_limits(client, settings):
    response = client.get("/transcribe/status")
    assert response.json() == {"available": True, "max_seconds": 30.0, "max_bytes": 1000}


def without_key(engine, monkeypatch):
    settings = Settings(_env_file=None, groq_api_key=None)
    monkeypatch.setattr("app.stt.get_settings", lambda: settings)
    monkeypatch.setattr("app.routers.transcribe.get_settings", lambda: settings)
    return TestClient(create_app(engine))


def test_without_a_key_transcribe_is_503(engine, monkeypatch):
    with without_key(engine, monkeypatch) as client:
        response = upload(client)
        status = client.get("/transcribe/status").json()
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
    assert status["available"] is False


def test_without_a_key_503_comes_before_validation(engine, monkeypatch):
    """The app hides the server option on 503, so a missing key must win over a bad upload."""
    with without_key(engine, monkeypatch) as client:
        response = upload(client, content_type="text/plain")
    assert response.status_code == 503


def test_with_a_key_the_groq_client_is_built():
    from app.stt import build_stt_client
    from app.stt.groq_client import GroqSTTClient

    client = build_stt_client(
        Settings(_env_file=None, groq_api_key="gsk_test", groq_stt_model="whisper-large-v3-turbo")
    )
    assert isinstance(client, GroqSTTClient)
    assert client._model == "whisper-large-v3-turbo"


def test_groq_client_drops_silent_segments_and_sends_language(monkeypatch):
    """Whisper invents text for silence; segments it marks as no-speech are left out."""
    from types import SimpleNamespace

    from app.stt.groq_client import GroqSTTClient

    stt = GroqSTTClient(api_key="gsk_test", model="whisper-large-v3")
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(
            text="rahim 120 taka baki Thank you.",
            duration=4.0,
            segments=[
                {"text": " rahim 120 taka baki", "no_speech_prob": 0.01, "avg_logprob": -0.2},
                {"text": " Thank you.", "no_speech_prob": 0.9, "avg_logprob": -1.4},
            ],
        )

    monkeypatch.setattr(stt._client.audio.transcriptions, "create", create)

    assert stt.transcribe(b"abc", "voice.webm", "en") == Transcript("rahim 120 taka baki", 4.0)
    assert sent["file"] == ("voice.webm", b"abc")
    assert sent["language"] == "en"
    assert sent["model"] == "whisper-large-v3"
    assert sent["response_format"] == "verbose_json"
