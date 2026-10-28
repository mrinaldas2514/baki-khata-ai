"""Idempotency-Key on /parse/confirm and /parse/confirm-many: a save sent again is saved once."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import Customer, IdempotencyKey, Transaction
from app.services import idempotency
from app.time_utils import utc_now

KEY = "0b6c9c1e-2f7a-4d4e-9f51-3c1d2a7e8b90"


def body(name="Tanvir", amount=90, **fields) -> dict:
    return {"raw_text": f"{name} {amount} baki", "type": "credit", "amount": amount,
            "new_customer": {"name": name}} | fields  # fmt: skip


def count(db, model) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


@pytest.fixture
def many_url(shop):
    return f"/shops/{shop['id']}/parse/confirm-many"


def test_the_same_save_sent_twice_is_saved_once(client, db, many_url):
    entries = {"entries": [body("Tanvir", 90), body("Rina", 40, type="payment")]}
    first = client.post(many_url, json=entries, headers={"Idempotency-Key": KEY})
    again = client.post(many_url, json=entries, headers={"Idempotency-Key": KEY})

    assert first.status_code == again.status_code == 201
    assert again.json() == first.json()
    assert again.headers["idempotent-replayed"] == "true"
    assert "idempotent-replayed" not in first.headers
    assert count(db, Transaction) == 2
    assert count(db, Customer) == 2  # Tanvir and Rina made once


def test_single_confirm_honours_the_key_too(client, db, shop):
    url = f"/shops/{shop['id']}/parse/confirm"
    first = client.post(url, json=body(), headers={"Idempotency-Key": KEY})
    again = client.post(url, json=body(), headers={"Idempotency-Key": KEY})
    assert again.status_code == 201
    assert again.json()["transaction"]["id"] == first.json()["transaction"]["id"]
    assert count(db, Transaction) == 1


def test_without_a_key_every_request_saves(client, db, shop, make_customer):
    rahim = make_customer("Rahim")
    url = f"/shops/{shop['id']}/parse/confirm"
    payment = {
        "raw_text": "rahim 50 dilo",
        "type": "payment",
        "amount": 50,
        "customer_id": rahim["id"],
    }
    assert client.post(url, json=payment).status_code == 201
    assert client.post(url, json=payment).status_code == 201
    assert count(db, Transaction) == 2


def test_a_key_with_different_data_is_refused(client, db, many_url):
    client.post(many_url, json={"entries": [body(amount=90)]}, headers={"Idempotency-Key": KEY})
    other = client.post(
        many_url, json={"entries": [body(amount=95)]}, headers={"Idempotency-Key": KEY}
    )
    assert other.status_code == 409
    assert "already used for a different request" in other.json()["detail"]
    assert count(db, Transaction) == 1


def test_keys_belong_to_one_shop(client, db, many_url, other_shop):
    entries = {"entries": [body()]}
    assert client.post(many_url, json=entries, headers={"Idempotency-Key": KEY}).status_code == 201
    response = client.post(
        f"/shops/{other_shop['id']}/parse/confirm-many",
        json=entries,
        headers={**other_shop["headers"], "Idempotency-Key": KEY},
    )
    assert response.status_code == 201
    assert "idempotent-replayed" not in response.headers
    assert count(db, Transaction) == 2


def test_a_failed_save_doesnt_use_up_the_key(client, db, many_url, make_customer):
    make_customer("Tanvir")  # the new customer clashes
    failed = client.post(many_url, json={"entries": [body()]}, headers={"Idempotency-Key": KEY})
    assert failed.status_code == 409
    assert count(db, IdempotencyKey) == 0
    fixed = {"entries": [body(new_customer={"name": "Tanvir", "note": "Notun"})]}
    assert client.post(many_url, json=fixed, headers={"Idempotency-Key": KEY}).status_code == 201


@pytest.mark.parametrize("key", ["short", "has spaces in it", "x" * 101, "key/with/a/slash"])
def test_badly_formed_keys_are_422(client, many_url, key):
    response = client.post(many_url, json={"entries": [body()]}, headers={"Idempotency-Key": key})
    assert response.status_code == 422


def find_late(monkeypatch):
    """_find misses the first time: the other request commits between our check and ours."""
    real_find = idempotency._find
    calls = []

    def find(db_, shop_id, key):
        calls.append(key)
        return None if len(calls) == 1 else real_find(db_, shop_id, key)

    monkeypatch.setattr(idempotency, "_find", find)
    return calls


def test_two_requests_with_one_key_at_once_save_once(client, db, shop, make_customer, monkeypatch):
    rahim = make_customer("Rahim")
    url = f"/shops/{shop['id']}/parse/confirm"
    payment = {
        "raw_text": "rahim 50 dilo",
        "type": "payment",
        "amount": 50,
        "customer_id": rahim["id"],
    }
    first = client.post(url, json=payment, headers={"Idempotency-Key": KEY})
    calls = find_late(monkeypatch)

    again = client.post(url, json=payment, headers={"Idempotency-Key": KEY})
    assert again.status_code == 201  # the unique key stopped the second save at its commit
    assert again.headers["idempotent-replayed"] == "true"
    assert again.json() == first.json()
    assert len(calls) == 2
    assert count(db, Transaction) == 1


def test_a_racing_retry_that_trips_over_its_own_new_customer_gets_the_first_answer(
    client, db, many_url, monkeypatch
):
    """The first try made Tanvir; the retry sees "Tanvir exists" before its key: still a replay."""
    entries = {"entries": [body()]}
    first = client.post(many_url, json=entries, headers={"Idempotency-Key": KEY})
    find_late(monkeypatch)

    again = client.post(many_url, json=entries, headers={"Idempotency-Key": KEY})
    assert again.status_code == 201, again.text
    assert again.json() == first.json()
    assert count(db, Customer) == 1


def test_old_keys_are_forgotten(client, db, shop, many_url):
    db.add(
        IdempotencyKey(
            shop_id=shop["id"], key="old-key-from-last-month", request_hash="x" * 64,
            status_code=201, response="{}", created_at=utc_now() - timedelta(days=40),
        )
    )  # fmt: skip
    db.commit()
    client.post(many_url, json={"entries": [body()]}, headers={"Idempotency-Key": KEY})
    db.expire_all()
    assert [k.key for k in db.scalars(select(IdempotencyKey))] == [KEY]


def test_keys_go_with_the_account(client, db, many_url):
    client.post(many_url, json={"entries": [body()]}, headers={"Idempotency-Key": KEY})
    assert (
        client.request("DELETE", "/auth/me", json={"password": "secret-pass-1"}).status_code == 204
    )
    assert count(db, IdempotencyKey) == 0


def test_cors_lets_the_app_send_the_key(anon_client):
    preflight = anon_client.options(
        "/shops/1/parse/confirm-many",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, idempotency-key",
        },
    )
    assert preflight.status_code == 200
