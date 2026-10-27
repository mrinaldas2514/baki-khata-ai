import json
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import build_engine, create_tables
from app.main import create_app
from app.models import Base
from app.stt import Transcript

# Defaults to in-memory SQLite. Set e.g. TEST_DATABASE_URL=postgresql+psycopg://... to run
# the same suite against PostgreSQL (use a throwaway database: tables are dropped).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


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


@pytest.fixture
def client(engine: Engine, fake_llm: FakeLLM, fake_stt: FakeSTT) -> Generator[TestClient]:
    with TestClient(create_app(engine, llm_client=fake_llm, stt_client=fake_stt)) as test_client:
        yield test_client


@pytest.fixture
def shop(client: TestClient) -> dict:
    response = client.post("/shops", json={"name": "Karim Store", "owner_name": "Karim"})
    assert response.status_code == 201
    return response.json()


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
