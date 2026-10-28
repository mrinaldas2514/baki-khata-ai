"""Accounts: register (with consent), login, logout, token expiry, settings, account deletion."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select

from app.models import Customer, Shop, Transaction, User
from app.privacy import CONSENT_VERSION
from app.security import create_access_token
from tests.conftest import auth_header, error_messages, registration

SECRET = "test-secret-for-the-test-suite-only-0123456789"  # tests/conftest.py


# --- Register -----------------------------------------------------------------------------


def test_register_creates_user_and_shop_and_logs_in(anon_client, db):
    before = datetime.now(UTC)
    response = anon_client.post(
        "/auth/register",
        json=registration(phone="01811-000000", email="Karim@Example.com", name=" Karim "),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    user = body["user"]
    assert user["name"] == "Karim"
    assert user["phone"] == "+8801811000000"  # normalized
    assert user["email"] == "karim@example.com"  # lowercased
    assert user["shop"]["name"] == "Karim Store"
    assert user["shop"]["owner_name"] == "Karim"
    assert user["ai_enabled"] is True
    assert user["consent_version"] == CONSENT_VERSION
    assert datetime.fromisoformat(user["consent_at"]) >= before.replace(microsecond=0)
    assert "password" not in response.text

    stored = db.scalar(select(User))
    assert stored.password_hash.startswith("$argon2id$")
    assert "secret-pass-1" not in stored.password_hash

    me = anon_client.get("/auth/me", headers=auth_header(body["access_token"]))
    assert me.json() == user


def test_register_with_email_only(register):
    user = register(phone=None, email="salma@example.com")["user"]
    assert user["phone"] is None
    assert user["email"] == "salma@example.com"


@pytest.mark.parametrize(
    ("fields", "field", "message"),
    [
        ({"consent": False}, "consent", "tick the box"),
        ({"consent_version": "2020-01"}, "consent_version", "privacy note has changed"),
        ({"password": "short"}, "password", "at least 8 characters"),
        ({"phone": "12345"}, "phone", "Bangladesh mobile number"),
        ({"email": "not-an-email"}, "email", "valid email"),
        ({"shop_name": "  "}, "shop_name", "at least 1 character"),
    ],
)
def test_register_validation(anon_client, fields, field, message):
    response = anon_client.post("/auth/register", json=registration(**fields))
    assert response.status_code == 422
    assert message in error_messages(response)[field]


def test_consent_is_required(anon_client, db):
    body = registration()
    del body["consent"]
    response = anon_client.post("/auth/register", json=body)
    assert response.status_code == 422
    assert error_messages(response)["consent"] == "Field required"
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(Shop)) == 0


def test_register_needs_phone_or_email(anon_client):
    response = anon_client.post("/auth/register", json=registration(phone=None))
    assert response.status_code == 422
    assert "phone number or an email" in error_messages(response)[None]


def test_register_same_phone_twice_is_409(anon_client, register):
    register(phone="01811000000")
    response = anon_client.post("/auth/register", json=registration(phone="+880 1811-000000"))
    assert response.status_code == 409


# --- Login --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "login", ["01811000000", "01811-000000", "+8801811000000", "8801811000000"]
)
def test_login_with_phone_in_any_format(anon_client, owner, login):
    response = anon_client.post("/auth/login", json={"login": login, "password": "secret-pass-1"})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == owner["user"]["id"]


def test_login_with_email_ignores_case(anon_client, register):
    register(phone=None, email="salma@example.com")
    response = anon_client.post(
        "/auth/login", json={"login": " Salma@Example.COM ", "password": "secret-pass-1"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "credentials",
    [
        {"login": "01811000000", "password": "wrong-password"},
        {"login": "01999999999", "password": "secret-pass-1"},
        {"login": "nobody@example.com", "password": "secret-pass-1"},
        {"login": "not a phone", "password": "secret-pass-1"},
    ],
)
def test_wrong_login_is_401_with_the_same_message(anon_client, owner, credentials):
    response = anon_client.post("/auth/login", json=credentials)
    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong phone/email or password"}


# --- Tokens -------------------------------------------------------------------------------


def test_token_expires_after_the_configured_time(owner):
    expires = datetime.fromisoformat(owner["expires_at"])
    assert timedelta(days=6, hours=23) < expires - datetime.now(UTC) <= timedelta(days=7)
    claims = jwt.decode(owner["access_token"], SECRET, algorithms=["HS256"])
    assert claims["sub"] == str(owner["user"]["id"])
    assert claims["shop"] == owner["user"]["shop"]["id"]


def test_no_token_is_401(anon_client, shop):
    for response in (
        anon_client.get("/auth/me"),
        anon_client.get(f"/shops/{shop['id']}/customers"),
        anon_client.get("/transcribe/status"),
    ):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_401(anon_client, owner):
    user = owner["user"]
    token, _ = create_access_token(
        user_id=user["id"],
        shop_id=user["shop"]["id"],
        secret=SECRET,
        expires_minutes=60,
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    response = anon_client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


@pytest.mark.parametrize("bad", ["garbage", "wrong-secret", "tampered"])
def test_forged_tokens_are_401(anon_client, owner, bad):
    user = owner["user"]
    if bad == "garbage":
        token = "not.a.token"
    elif bad == "wrong-secret":
        token, _ = create_access_token(
            user_id=user["id"],
            shop_id=user["shop"]["id"],
            secret="some-other-secret-that-is-long-enough-123",
            expires_minutes=60,
        )
    else:
        claims = jwt.decode(owner["access_token"], options={"verify_signature": False})
        token = jwt.encode(
            {**claims, "shop": 999}, "an-attackers-guess-at-the-secret-0123", algorithm="HS256"
        )
    assert anon_client.get("/auth/me", headers=auth_header(token)).status_code == 401


def test_logout_stops_only_that_token(anon_client, owner):
    other_login = anon_client.post(
        "/auth/login", json={"login": "01811000000", "password": "secret-pass-1"}
    ).json()
    headers = auth_header(owner["access_token"])

    assert anon_client.post("/auth/logout", headers=headers).status_code == 204
    response = anon_client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert "Logged out" in response.json()["detail"]
    # The login on another phone still works.
    assert (
        anon_client.get("/auth/me", headers=auth_header(other_login["access_token"])).status_code
        == 200
    )


# --- Settings and account deletion --------------------------------------------------------


def test_turn_ai_off_and_on(client):
    assert client.patch("/auth/me", json={"ai_enabled": False}).json()["ai_enabled"] is False
    assert client.get("/auth/me").json()["ai_enabled"] is False
    assert client.patch("/auth/me", json={"ai_enabled": True}).json()["ai_enabled"] is True


def test_delete_account_needs_the_password(client, db, customer, add_txn):
    add_txn(customer["id"], "credit", 100)
    response = client.request("DELETE", "/auth/me", json={"password": "wrong-password"})
    assert response.status_code == 403
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1
    assert client.get("/auth/me").status_code == 200  # still logged in


def test_delete_account_removes_everything(
    client, anon_client, db, shop, other_shop, customer, add_txn
):
    add_txn(customer["id"], "credit", 100)
    client.post(
        f"/shops/{other_shop['id']}/customers",
        json={"name": "Keep me"},
        headers=other_shop["headers"],
    )

    response = client.request("DELETE", "/auth/me", json={"password": "secret-pass-1"})

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Shop, shop["id"]) is None
    assert db.scalar(select(func.count()).select_from(Transaction)) == 0
    assert [c.name for c in db.scalars(select(Customer))] == ["Keep me"]  # other shops untouched
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert client.get("/auth/me").status_code == 401
    login = anon_client.post(
        "/auth/login", json={"login": "01811000000", "password": "secret-pass-1"}
    )
    assert login.status_code == 401
