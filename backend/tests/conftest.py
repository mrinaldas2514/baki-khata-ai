import json
import os
from collections.abc import Generator

# Every app the tests build signs tokens with the same secret, so a login made with one test
# app also works with another one on the same database. Set before app.config is imported.
os.environ.setdefault("JWT_SECRET", "test-secret-for-the-test-suite-only-0123456789")

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import build_engine, create_tables
from app.main import create_app
from app.models import Base
from app.privacy import CONSENT_VERSION
from app.stt import Transcript

# Defaults to in-memory SQLite. Set e.g. TEST_DATABASE_URL=postgresql+psycopg://... to run
# the same suite against PostgreSQL (use a throwaway database: tables are dropped).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture(autouse=True)
def cheap_password_hashing(monkeypatch):
    """argon2's real settings take ~50 ms and 64 MiB per hash; tests hash a lot of passwords."""
    monkeypatch.setattr(
        "app.security.password_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )
    monkeypatch.setattr("app.security._dummy_hash", None)


@pytest.fixture
def engine() -> Generator[Engine]:
    if TEST_DATABASE_URL == "sqlite://":
        # StaticPool shares the single in-memory connection across threads.
        engine = build_engine(TEST_DATABASE_URL, poolclass=StaticPool)
    else:
        engine = build_engine(TEST_DATABASE_URL)
    create_tables(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


class FakeLLM:
    """Stands in for the real model so tests never call Groq or need an API key.

    Queue answers with `reply(...)`: a dict is sent as JSON, a str as-is, an exception is raised.
    """

    def __init__(self) -> None:
        self.answers: list[object] = []
        self.calls: list[list[dict]] = []

    def reply(self, *answers: object) -> None:
        self.answers.extend(answers)

    def complete_json(self, messages: list[dict]) -> str:
        self.calls.append([dict(m) for m in messages])
        assert self.answers, "FakeLLM was called more times than answers were queued"
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)


class FakeSTT:
    """Stands in for Whisper. Queue answers with `reply(...)`: a Transcript, a str, or an exception."""

    def __init__(self) -> None:
        self.answers: list[object] = []
        self.calls: list[dict] = []

    def reply(self, *answers: object) -> None:
        self.answers.extend(answers)

    def transcribe(self, audio: bytes, filename: str, language=None) -> Transcript:
        self.calls.append({"audio": audio, "filename": filename, "language": language})
        assert self.answers, "FakeSTT was called more times than answers were queued"
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, Transcript) else Transcript(text=str(answer))


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_stt() -> FakeSTT:
    return FakeSTT()


def registration(
    phone: str | None = "01811000000", password: str = "secret-pass-1", **fields
) -> dict:
    """A valid POST /auth/register body."""
    body = {
        "name": "Karim",
        "shop_name": "Karim Store",
        "phone": phone,
        "password": password,
        "consent": True,
        "consent_version": CONSENT_VERSION,
    }
    return {**body, **fields}


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app(engine: Engine, fake_llm: FakeLLM, fake_stt: FakeSTT) -> FastAPI:
    return create_app(engine, llm_client=fake_llm, stt_client=fake_stt)


@pytest.fixture
def anon_client(app: FastAPI) -> Generator[TestClient]:
    """Not logged in."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register(anon_client: TestClient):
    """Register a shopkeeper; returns the /auth/register answer (access_token, user)."""

    def _register(**fields) -> dict:
        response = anon_client.post("/auth/register", json=registration(**fields))
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest.fixture
def owner(register) -> dict:
    """The shopkeeper `client` is logged in as."""
    return register()


@pytest.fixture
def owner_headers(owner: dict) -> dict[str, str]:
    return auth_header(owner["access_token"])


@pytest.fixture
def client(app: FastAPI, owner: dict) -> Generator[TestClient]:
    """Logged in as `owner`, the owner of `shop`."""
    with TestClient(app, headers=auth_header(owner["access_token"])) as test_client:
        yield test_client


@pytest.fixture
def shop(owner: dict) -> dict:
    return owner["user"]["shop"]


@pytest.fixture
def other_shop(register) -> dict:
    """A second shopkeeper's shop, with `headers` to act as that shopkeeper."""
    other = register(phone="01911000000", name="X", shop_name="Other")
    return {**other["user"]["shop"], "headers": auth_header(other["access_token"])}


@pytest.fixture
def make_customer(client: TestClient, shop: dict):
    def _make(name: str = "Rahim", **fields) -> dict:
        response = client.post(f"/shops/{shop['id']}/customers", json={"name": name, **fields})
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def customer(make_customer) -> dict:
    return make_customer("Rahim", phone="01711-000000", note="Bazar road")


@pytest.fixture
def add_txn(client: TestClient, shop: dict):
    def _add(customer_id: int, type_: str, amount: int, **fields) -> dict:
        response = client.post(
            f"/shops/{shop['id']}/customers/{customer_id}/transactions",
            json={"type": type_, "amount": amount, **fields},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _add


def error_messages(response) -> dict[str | None, str]:
    """Map field -> message from our validation error format."""
    return {e["field"]: e["message"] for e in response.json()["errors"]}
