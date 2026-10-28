"""Rate limits on login, register, parse and transcribe, with a friendly Banglish message."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rate_limit import Limit, RateLimitedError, RateLimiter
from tests.conftest import auth_header, registration


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_allows_n_per_window_then_says_how_long_to_wait():
    clock = Clock()
    limiter = RateLimiter({"login": Limit(3, 60)}, clock=clock)
    for _ in range(3):
        limiter.hit("login", "1.2.3.4")
    with pytest.raises(RateLimitedError) as exc_info:
        limiter.hit("login", "1.2.3.4")
    assert exc_info.value.retry_after == 60
    limiter.hit("login", "5.6.7.8")  # someone else is not affected

    clock.now += 30
    with pytest.raises(RateLimitedError) as exc_info:
        limiter.hit("login", "1.2.3.4")
    assert exc_info.value.retry_after == 30

    clock.now += 31  # the first tries have left the window
    limiter.hit("login", "1.2.3.4")


def test_unknown_or_disabled_limits_never_block():
    limiter = RateLimiter({})
    for _ in range(100):
        limiter.hit("login", "x")


@pytest.fixture
def strict(engine, monkeypatch, fake_llm, fake_stt):
    settings = Settings(
        _env_file=None,
        rate_limit_login_per_minute=3,
        rate_limit_register_per_hour=2,
        rate_limit_parse_per_minute=2,
        rate_limit_transcribe_per_minute=1,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    with TestClient(create_app(engine, llm_client=fake_llm, stt_client=fake_stt)) as client:
        yield client


def assert_limited(response):
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    body = response.json()
    assert body["retry_after"] > 0
    assert body["detail"].startswith("Onek bar chesta hoyeche.")


def test_login_is_limited(strict):
    strict.post("/auth/register", json=registration())
    wrong = {"login": "01811000000", "password": "wrong-password"}
    for _ in range(3):
        assert strict.post("/auth/login", json=wrong).status_code == 401
    assert_limited(strict.post("/auth/login", json=wrong))
    # Even the right password waits: guessing must stay slow.
    assert_limited(strict.post("/auth/login", json={**wrong, "password": "secret-pass-1"}))


def test_register_is_limited(strict):
    assert strict.post("/auth/register", json=registration(phone="01811000001")).status_code == 201
    assert strict.post("/auth/register", json=registration(phone="01811000002")).status_code == 201
    assert_limited(strict.post("/auth/register", json=registration(phone="01811000003")))


def test_parse_and_transcribe_are_limited_per_shop(strict, fake_llm, fake_stt):
    owner = strict.post("/auth/register", json=registration()).json()
    headers = auth_header(owner["access_token"])
    url = f"/shops/{owner['user']['shop']['id']}/parse"
    answer = {"customer_name": "k", "amount": 5, "type": "credit", "item": None, "confidence": 1}
    fake_llm.reply(answer, answer)
    for _ in range(2):
        assert strict.post(url, json={"text": "k 5 baki"}, headers=headers).status_code == 200
    assert_limited(strict.post(url, json={"text": "k 5 baki"}, headers=headers))
    assert len(fake_llm.calls) == 2  # the limited request never reached the AI

    fake_stt.reply("k 5 baki")
    upload = {"files": {"file": ("v.webm", b"audio", "audio/webm")}, "headers": headers}
    assert strict.post("/transcribe", **upload).status_code == 200
    assert_limited(strict.post("/transcribe", **upload))
    assert len(fake_stt.calls) == 1


def test_limits_can_be_switched_off(engine, monkeypatch):
    settings = Settings(_env_file=None, rate_limit_enabled=False, rate_limit_login_per_minute=1)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    with TestClient(create_app(engine)) as client:
        for _ in range(5):
            response = client.post("/auth/login", json={"login": "x@y.z", "password": "nope"})
            assert response.status_code == 401
