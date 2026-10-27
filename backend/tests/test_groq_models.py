"""Clear errors when Groq rejects GROQ_MODEL / GROQ_STT_MODEL (e.g. a retired model)."""

import logging
from types import SimpleNamespace

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.groq_models import check_configured_models, model_rejection
from app.llm import LLMProviderError
from app.llm.groq_client import GroqLLMClient
from app.main import create_app
from app.stt import STTProviderError
from app.stt.groq_client import GroqSTTClient

REQUEST = httpx.Request("GET", "https://api.groq.com/openai/v1/models/x")


def api_error(cls, status: int, code: str | None, message: str):
    body = {"error": {"message": message, "type": "invalid_request_error", "code": code}}
    return cls(message, response=httpx.Response(status, request=REQUEST), body=body)


def not_found(model: str):
    return api_error(
        groq.NotFoundError, 404, "model_not_found", f"The model `{model}` does not exist."
    )


def decommissioned(model: str):
    return api_error(
        groq.BadRequestError, 400, "model_decommissioned",
        f"The model `{model}` has been decommissioned and is no longer supported.",
    )  # fmt: skip


class FakeModels:
    def __init__(self, errors: dict[str, Exception]):
        self.errors = errors
        self.asked: list[str] = []

    def retrieve(self, model: str):
        self.asked.append(model)
        if model in self.errors:
            raise self.errors[model]
        return SimpleNamespace(id=model)


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, groq_api_key="gsk_test", **overrides)


def test_default_models():
    defaults = Settings(_env_file=None)
    assert defaults.groq_model == "openai/gpt-oss-120b"
    assert defaults.groq_stt_model == "whisper-large-v3"


def test_retired_chat_model_is_logged_clearly(caplog):
    models = FakeModels({"llama-3.3-70b-versatile": decommissioned("llama-3.3-70b-versatile")})
    with caplog.at_level(logging.ERROR, logger="app.groq_models"):
        rejected = check_configured_models(
            settings(groq_model="llama-3.3-70b-versatile"), SimpleNamespace(models=models)
        )
    assert rejected == ["GROQ_MODEL"]
    assert models.asked == ["llama-3.3-70b-versatile", "whisper-large-v3"]
    [record] = caplog.records
    assert "Groq rejected GROQ_MODEL='llama-3.3-70b-versatile'" in record.message
    assert "decommissioned" in record.message
    assert "Set GROQ_MODEL in backend/.env" in record.message
    assert "https://console.groq.com/docs/models" in record.message


def test_unknown_stt_model_is_logged_clearly(caplog):
    models = FakeModels({"whisper-huge": not_found("whisper-huge")})
    with caplog.at_level(logging.ERROR, logger="app.groq_models"):
        rejected = check_configured_models(
            settings(groq_stt_model="whisper-huge"), SimpleNamespace(models=models)
        )
    assert rejected == ["GROQ_STT_MODEL"]
    assert "Set GROQ_STT_MODEL in backend/.env" in caplog.records[0].message


def test_good_models_log_nothing(caplog):
    with caplog.at_level(logging.WARNING):
        assert check_configured_models(settings(), SimpleNamespace(models=FakeModels({}))) == []
    assert caplog.records == []


def test_chat_model_is_not_checked_with_the_demo_parser():
    models = FakeModels({})
    check_configured_models(settings(llm_provider="fake"), SimpleNamespace(models=models))
    assert models.asked == ["whisper-large-v3"]


def test_no_key_no_check():
    models = FakeModels({})
    assert check_configured_models(Settings(_env_file=None), SimpleNamespace(models=models)) == []
    assert models.asked == []


def test_bad_key_and_network_errors_never_stop_startup(caplog):
    bad_key = api_error(groq.AuthenticationError, 401, "invalid_api_key", "Invalid API Key")
    offline = groq.APIConnectionError(request=REQUEST)
    with caplog.at_level(logging.WARNING, logger="app.groq_models"):
        for error in (bad_key, offline):
            models = FakeModels({"openai/gpt-oss-120b": error})
            assert check_configured_models(settings(), SimpleNamespace(models=models)) == []
    assert "rejected GROQ_API_KEY" in caplog.records[0].message
    assert "Could not reach Groq" in caplog.records[1].message


def test_rate_limit_is_not_a_model_problem():
    assert model_rejection(api_error(groq.RateLimitError, 429, "rate_limit_exceeded", "Slow down")) is None


def test_startup_runs_the_check_when_a_key_is_set(engine, monkeypatch):
    checked = []
    configured = settings()
    monkeypatch.setattr("app.main.get_settings", lambda: configured)
    monkeypatch.setattr("app.main.start_model_check", checked.append)
    with TestClient(create_app(engine)):
        pass
    assert checked == [configured]


# --- the same message when a request fails later -----------------------------------------


def test_chat_request_with_a_retired_model_logs_the_fix(caplog):
    client = GroqLLMClient(api_key="gsk_test", model="llama-3.3-70b-versatile")
    error = decommissioned("llama-3.3-70b-versatile")

    def create(**_kwargs):
        raise error

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with caplog.at_level(logging.ERROR, logger="app.groq_models"), pytest.raises(LLMProviderError):
        client.complete_json([{"role": "user", "content": "rahim 100 baki"}])
    assert "Set GROQ_MODEL in backend/.env" in caplog.records[0].message


def test_transcription_with_an_unknown_model_logs_the_fix(caplog):
    client = GroqSTTClient(api_key="gsk_test", model="whisper-huge")

    def create(**_kwargs):
        raise not_found("whisper-huge")

    client._client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    with caplog.at_level(logging.ERROR, logger="app.groq_models"), pytest.raises(STTProviderError):
        client.transcribe(b"audio", "voice.webm")
    assert "Set GROQ_STT_MODEL in backend/.env" in caplog.records[0].message


@pytest.mark.parametrize(
    ("model", "extra"),
    [
        ("openai/gpt-oss-120b", {"reasoning_effort": "low", "max_completion_tokens": 1024}),
        ("some/other-model", {"max_completion_tokens": 400}),
    ],
)
def test_reasoning_models_get_low_effort_and_room_to_think(model, extra):
    client = GroqLLMClient(api_key="gsk_test", model=model)
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        message = SimpleNamespace(content='{"ok": true}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert client.complete_json([{"role": "user", "content": "hi"}]) == '{"ok": true}'
    assert sent["response_format"] == {"type": "json_object"}
    assert {k: sent.get(k) for k in extra} == extra
    if "reasoning_effort" not in extra:
        assert "reasoning_effort" not in sent
