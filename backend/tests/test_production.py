"""Production settings and HTTP hardening: refuse unsafe settings, security headers, body size
limits, no debug output, and a health check that asks the database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import build_engine
from app.main import ProductionConfigError, create_app

SECRET = "production-secret-for-tests-0123456789abcdef"


def production(**overrides) -> Settings:
    values = {
        "environment": "production",
        "jwt_secret": SECRET,
        "database_url": "postgresql://baki:pw@db.internal:5432/baki",
        "cors_origins": "https://baki-khata.vercel.app",
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.fixture
def use_settings(monkeypatch):
    def _use(settings: Settings) -> Settings:
        monkeypatch.setattr("app.main.get_settings", lambda: settings)
        return settings

    return _use


# --- What production requires -------------------------------------------------------------


def test_safe_production_settings_have_no_problems():
    assert production().production_problems() == []


def test_development_has_no_requirements():
    assert Settings(_env_file=None).production_problems() == []
    assert Settings(_env_file=None).allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_every_problem_is_listed_at_once():
    # Blank JWT_SECRET: the test suite sets one in the environment (conftest.py).
    settings = Settings(_env_file=None, environment="production", sql_echo=True, jwt_secret="")
    problems = "\n".join(settings.production_problems())
    assert "JWT_SECRET is not set" in problems
    assert "DATABASE_URL must be a PostgreSQL database" in problems
    assert "CORS_ORIGINS is not set" in problems
    assert "SQL_ECHO must be false" in problems
    assert settings.allowed_origins == []  # no localhost default in production


@pytest.mark.parametrize(
    ("origins", "problem"),
    [
        ("*", "not '*'"),
        ("https://*.vercel.app", "not '*'"),
        ("http://baki-khata.example", "use https://"),
        ("https://baki-khata.example/app", "scheme://host[:port] only"),
    ],
)
def test_cors_must_be_exact_https_origins(origins, problem):
    assert any(problem in p for p in production(cors_origins=origins).production_problems())


def test_localhost_over_http_is_allowed_for_docker_compose():
    assert production(cors_origins="http://localhost:8080").production_problems() == []


@pytest.mark.parametrize(
    "url", ["postgres://u:p@host/db", "postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"]
)
def test_postgres_urls_get_the_psycopg_driver(url):
    assert Settings(_env_file=None, database_url=url).database_url == "postgresql+psycopg://u:p@host/db"


def test_the_app_refuses_to_start_with_unsafe_production_settings(engine, use_settings):
    use_settings(Settings(_env_file=None, environment="production", jwt_secret=SECRET))
    with pytest.raises(ProductionConfigError) as error:
        create_app(engine)
    message = str(error.value)
    assert "DATABASE_URL" in message and "CORS_ORIGINS" in message
    assert "JWT_SECRET" not in message  # only what's actually wrong


def test_production_has_no_api_docs_and_sends_hsts(engine, use_settings):
    use_settings(production())
    with TestClient(create_app(engine)) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404, path
        health = client.get("/health")
    assert health.json() == {"status": "ok", "database": "ok"}
    assert health.headers["strict-transport-security"].startswith("max-age=31536000")


def test_production_cors_allows_only_the_configured_frontend(engine, use_settings):
    use_settings(production())
    with TestClient(create_app(engine)) as client:
        ok = client.get("/health", headers={"Origin": "https://baki-khata.vercel.app"})
        local = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "https://baki-khata.vercel.app"
    assert "access-control-allow-origin" not in local.headers


# --- Headers ------------------------------------------------------------------------------


def test_security_headers_on_every_answer(client, shop):
    for response in (client.get("/health"), client.get(f"/shops/{shop['id']}/customers")):
        headers = response.headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
        assert headers["cache-control"] == "no-store"
        assert "strict-transport-security" not in headers  # development: plain http


def test_api_docs_still_work_in_development(anon_client):
    docs = anon_client.get("/docs")
    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers  # it loads scripts


def test_cors_preflight_allows_the_headers_the_app_sends(anon_client):
    def preflight(header: str):
        return anon_client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": header,
            },
        )

    assert preflight("authorization, content-type, idempotency-key").status_code == 200
    assert preflight("x-something-else").status_code == 400


# --- Request size ---------------------------------------------------------------------------


def test_too_large_bodies_are_refused_with_413(anon_client):
    big = b'{"login": "' + b"x" * (200 * 1024) + b'", "password": "y"}'
    response = anon_client.post(
        "/auth/login",
        content=big,
        headers={"content-type": "application/json", "Origin": "http://localhost:5173"},
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]
    # Inside CORS, so the app can read the answer.
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_too_large_chunked_bodies_are_refused_too(anon_client):
    def chunks():
        for _ in range(300):
            yield b"x" * 1024

    response = anon_client.post(
        "/auth/login", content=chunks(), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


def test_voice_uploads_may_be_bigger(client, fake_stt):
    fake_stt.reply("rahim 100 baki")
    audio = b"\x1a\x45\xdf\xa3" + b"0" * (300 * 1024)  # 300 KB: over the JSON limit, under audio's
    response = client.post(
        "/transcribe", files={"file": ("voice.webm", audio, "audio/webm")}, data={"language": "bn-BD"}
    )
    assert response.status_code == 200, response.text


# --- No debug output ------------------------------------------------------------------------


def test_unexpected_errors_say_nothing_about_the_cause(engine, caplog):
    app = create_app(engine, llm_client=object(), stt_client=object())

    @app.get("/boom")
    def boom():
        raise RuntimeError("customer Rahim owes 500")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on the server. Please try again."}
    assert "Rahim" not in response.text


def test_database_errors_dont_carry_the_values():
    assert build_engine("sqlite://", poolclass=StaticPool).hide_parameters is True
    assert build_engine("sqlite://", echo=True, poolclass=StaticPool).hide_parameters is False


# --- Health -----------------------------------------------------------------------------------


def test_health_is_503_when_the_database_is_unreachable(tmp_path, caplog):
    unreachable = build_engine(f"sqlite:///{tmp_path}/no/such/dir/baki.db")
    app = create_app(unreachable, llm_client=object(), stt_client=object(), check_migrations=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}
    assert "database is unreachable (OperationalError)" in caplog.text
