"""Shopkeeper A can't read, change or delete anything of shopkeeper B's, and learns nothing.

Every way in answers 404, the same as for a shop or record that doesn't exist.
"""

import pytest
from sqlalchemy import func, select

from app.models import Customer, Transaction


@pytest.fixture
def b_data(client, other_shop):
    """Shop B with a customer and a transaction, created by B."""
    as_b = {"headers": other_shop["headers"]}
    customer = client.post(
        f"/shops/{other_shop['id']}/customers",
        json={"name": "Secret Customer", "phone": "01911222333"},
        **as_b,
    ).json()
    txn = client.post(
        f"/shops/{other_shop['id']}/customers/{customer['id']}/transactions",
        json={"type": "credit", "amount": 777, "raw_text": "secret customer 777 baki"},
        **as_b,
    ).json()
    return {"shop": other_shop["id"], "customer": customer["id"], "txn": txn["id"]}


def b_requests(b: dict, a_shop: int) -> list[tuple[str, str, dict | None]]:
    s, c, t = b["shop"], b["customer"], b["txn"]
    txn_body = {"type": "credit", "amount": 5}
    confirm = {"raw_text": "x 5 baki", "type": "credit", "amount": 5}
    return [
        # B's shop id in the URL (A's token)
        ("GET", f"/shops/{s}", None),
        ("GET", f"/shops/{s}/customers", None),
        ("POST", f"/shops/{s}/customers", {"name": "Intruder"}),
        ("GET", f"/shops/{s}/customers/{c}", None),
        ("PATCH", f"/shops/{s}/customers/{c}", {"name": "Hacked"}),
        ("DELETE", f"/shops/{s}/customers/{c}", None),
        ("GET", f"/shops/{s}/customers/{c}/transactions", None),
        ("POST", f"/shops/{s}/customers/{c}/transactions", txn_body),
        ("POST", f"/shops/{s}/customers/{c}/reminder", None),
        ("GET", f"/shops/{s}/transactions", None),
        ("GET", f"/shops/{s}/transactions/{t}", None),
        ("PATCH", f"/shops/{s}/transactions/{t}", {"amount": 1}),
        ("DELETE", f"/shops/{s}/transactions/{t}", None),
        ("GET", f"/shops/{s}/dashboard", None),
        ("GET", f"/shops/{s}/export.csv", None),
        ("POST", f"/shops/{s}/parse", {"text": "rahim 5 baki"}),
        ("POST", f"/shops/{s}/parse/confirm", {**confirm, "customer_id": c}),
        # A's own shop id, B's record ids
        ("GET", f"/shops/{a_shop}/customers/{c}", None),
        ("PATCH", f"/shops/{a_shop}/customers/{c}", {"name": "Hacked"}),
        ("DELETE", f"/shops/{a_shop}/customers/{c}", None),
        ("GET", f"/shops/{a_shop}/customers/{c}/transactions", None),
        ("POST", f"/shops/{a_shop}/customers/{c}/transactions", txn_body),
        ("POST", f"/shops/{a_shop}/customers/{c}/reminder", None),
        ("GET", f"/shops/{a_shop}/transactions/{t}", None),
        ("PATCH", f"/shops/{a_shop}/transactions/{t}", {"amount": 1}),
        ("DELETE", f"/shops/{a_shop}/transactions/{t}", None),
        ("POST", f"/shops/{a_shop}/parse/confirm", {**confirm, "customer_id": c}),
    ]


def test_a_cannot_reach_b_by_any_endpoint(client, shop, b_data, db):
    for method, url, body in b_requests(b_data, shop["id"]):
        response = client.request(method, url, json=body)
        assert response.status_code == 404, (method, url, response.status_code)
        assert "Secret" not in response.text and "777" not in response.text, (method, url)

    # Nothing of B's changed.
    customer = db.get(Customer, b_data["customer"])
    txn = db.get(Transaction, b_data["txn"])
    assert customer.name == "Secret Customer"
    assert (txn.amount, txn.shop_id) == (777, b_data["shop"])
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1
    assert db.scalar(select(func.count()).select_from(Customer)) == 1


def test_another_shops_404_looks_like_a_missing_shop(client, other_shop):
    missing = client.get("/shops/999999/customers")
    other = client.get(f"/shops/{other_shop['id']}/customers")
    assert other.status_code == missing.status_code == 404
    assert other.json() == {"detail": f"Shop {other_shop['id']} not found"}


def test_b_still_sees_its_own_data(client, b_data, other_shop):
    as_b = {"headers": other_shop["headers"]}
    response = client.get(f"/shops/{b_data['shop']}/customers/{b_data['customer']}", **as_b)
    assert response.status_code == 200
    assert response.json()["balance"] == 777


def test_a_export_has_none_of_b(client, shop, b_data, make_customer):
    make_customer("Mine")
    csv = client.get(f"/shops/{shop['id']}/export.csv").text
    assert "Mine" in csv
    assert "Secret" not in csv and "777" not in csv


def test_a_list_search_and_recent_never_show_b(client, shop, b_data):
    assert client.get(f"/shops/{shop['id']}/customers", params={"search": "secret"}).json() == []
    assert client.get(f"/shops/{shop['id']}/transactions").json() == []
    assert client.get(f"/shops/{shop['id']}/dashboard").json()["total_outstanding"] == 0
