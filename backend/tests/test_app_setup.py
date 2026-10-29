"""App-level wiring: CORS for the frontend and the demo seed script."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import Customer, Shop, Transaction
from app.seed import CUSTOMERS, DEMO_PASSWORD, DEMO_PHONE, TRANSACTIONS, seed


def test_cors_allows_the_configured_frontend_origin(client):
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_lets_the_app_read_the_csv_name_and_retry_after(client, shop):
    response = client.get(
        f"/shops/{shop['id']}/export.csv", headers={"Origin": "http://localhost:5173"}
    )
    exposed = response.headers["access-control-expose-headers"]
    assert "Content-Disposition" in exposed and "Retry-After" in exposed


def test_cors_rejects_other_origins(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_come_from_env(engine, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://192.168.0.5:5173/, https://app.example ")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://192.168.0.5:5173", "https://app.example"]
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    with TestClient(create_app(engine)) as client:
        response = client.get("/health", headers={"Origin": "https://app.example"})
    assert response.headers["access-control-allow-origin"] == "https://app.example"


def test_seed_creates_demo_shop_once(db: Session):
    shop = seed(db)
    assert db.scalar(select(func.count()).select_from(Customer)) == len(CUSTOMERS)
    assert db.scalar(select(func.count()).select_from(Transaction)) == len(TRANSACTIONS)

    assert seed(db).id == shop.id  # running it again changes nothing
    assert db.scalar(select(func.count()).select_from(Shop)) == 1
    assert db.scalar(select(func.count()).select_from(Transaction)) == len(TRANSACTIONS)


def test_seed_reset_recreates_demo_shop(db: Session):
    seed(db)
    seed(db, reset=True)
    assert db.scalar(select(func.count()).select_from(Shop)) == 1
    assert db.scalar(select(func.count()).select_from(Customer)) == len(CUSTOMERS)
    assert db.scalar(select(func.count()).select_from(Transaction)) == len(TRANSACTIONS)


def test_seeded_shop_works_with_the_demo_parser(engine, monkeypatch):
    """End to end without an API key: seed, then parse with LLM_PROVIDER=fake."""
    with Session(engine, expire_on_commit=False) as db:
        shop_id = seed(db).id
    monkeypatch.setattr(
        "app.llm.get_settings", lambda: Settings(_env_file=None, llm_provider="fake")
    )
    with TestClient(create_app(engine)) as client:
        login = client.post("/auth/login", json={"login": DEMO_PHONE, "password": DEMO_PASSWORD})
        assert login.json()["user"]["shop"]["id"] == shop_id
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        rahim = client.post(f"/shops/{shop_id}/parse", json={"text": "rahim 100 taka baki"})
        salma = client.post(f"/shops/{shop_id}/parse", json={"text": "salma apa 200 dilo"})
        new = client.post(f"/shops/{shop_id}/parse", json={"text": "Tanvir 90 taka baki"})
    assert rahim.json()["match"]["status"] == "ambiguous"  # two Rahims in the demo shop
    assert salma.json()["match"]["status"] == "exact"
    assert salma.json()["match"]["customer"]["balance"] == 200
    assert new.json()["match"]["status"] == "new"


def test_seed_demo_on_start_creates_the_demo_login_once(engine, monkeypatch, fake_llm, fake_stt):
    """SEED_DEMO_ON_START=true: the demo login works on a fresh database, and restarts keep it."""
    monkeypatch.setenv("SEED_DEMO_ON_START", "true")
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None))
    for _restart in range(2):
        with TestClient(create_app(engine, llm_client=fake_llm, stt_client=fake_stt)) as client:
            login = client.post(
                "/auth/login", json={"login": DEMO_PHONE, "password": DEMO_PASSWORD}
            )
            assert login.status_code == 200, login.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Shop)) == 1
        assert db.scalar(select(func.count()).select_from(Transaction)) == len(TRANSACTIONS)


def test_no_demo_shop_unless_asked(engine, monkeypatch, fake_llm, fake_stt):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None))
    with TestClient(create_app(engine, llm_client=fake_llm, stt_client=fake_stt)):
        pass
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Shop)) == 0
