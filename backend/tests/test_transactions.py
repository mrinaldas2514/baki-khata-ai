from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import error_messages


def iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def txn_url(shop, customer):
    return f"/shops/{shop['id']}/customers/{customer['id']}/transactions"


# --- create -----------------------------------------------------------------


def test_create_credit(client, shop, customer, txn_url):
    response = client.post(
        txn_url,
        json={
            "type": "credit",
            "amount": 250,
            "item": "2 kg chal",
            "raw_text": "Rahim 2 kg chal nilo 250 taka baki",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "credit"
    assert body["amount"] == 250
    assert body["item"] == "2 kg chal"
    assert body["raw_text"] == "Rahim 2 kg chal nilo 250 taka baki"
    assert body["shop_id"] == shop["id"]
    assert body["customer_id"] == customer["id"]
    assert body["customer_balance"] == 250
    created = datetime.fromisoformat(body["created_at"])
    assert abs(created - datetime.now(UTC)) < timedelta(minutes=1)


def test_create_payment_reduces_balance(client, txn_url):
    client.post(txn_url, json={"type": "credit", "amount": 500})
    response = client.post(txn_url, json={"type": "payment", "amount": 200})
    assert response.status_code == 201
    assert response.json()["customer_balance"] == 300
    assert response.json()["item"] is None


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        (0, "Amount must be greater than 0"),
        (-50, "Amount must be greater than 0"),
        (10.5, "Input should be a valid integer"),
        ("100", "Input should be a valid integer"),
        (True, "Input should be a valid integer"),
        (None, "Input should be a valid integer"),
        (10_000_001, "Amount must not be more than 10000000 taka"),
    ],
)
def test_invalid_amount(client, txn_url, amount, message):
    response = client.post(txn_url, json={"type": "credit", "amount": amount})
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid request data"
    assert error_messages(response)["amount"] == message


def test_missing_amount(client, txn_url):
    response = client.post(txn_url, json={"type": "credit"})
    assert error_messages(response)["amount"] == "Field required"


def test_invalid_type(client, txn_url):
    response = client.post(txn_url, json={"type": "loan", "amount": 100})
    assert response.status_code == 422
    assert "credit" in error_messages(response)["type"]


def test_backdated_transaction(client, txn_url):
    when = datetime.now(UTC) - timedelta(days=3)
    response = client.post(txn_url, json={"type": "credit", "amount": 10, "created_at": iso(when)})
    assert response.status_code == 201
    assert datetime.fromisoformat(response.json()["created_at"]) == when


def test_naive_date_is_read_as_shop_local_time(client, txn_url):
    # Default timezone is Asia/Dhaka (UTC+6).
    response = client.post(
        txn_url, json={"type": "credit", "amount": 10, "created_at": "2026-01-15T10:00:00"}
    )
    assert response.status_code == 201
    assert datetime.fromisoformat(response.json()["created_at"]) == datetime(
        2026, 1, 15, 4, 0, tzinfo=UTC
    )


def test_future_date_is_rejected(client, txn_url):
    future = datetime.now(UTC) + timedelta(days=1)
    response = client.post(txn_url, json={"type": "credit", "amount": 10, "created_at": iso(future)})
    assert response.status_code == 422
    assert error_messages(response)["created_at"] == "Date cannot be in the future"


def test_create_for_missing_customer(client, shop):
    response = client.post(
        f"/shops/{shop['id']}/customers/999/transactions", json={"type": "credit", "amount": 10}
    )
    assert response.status_code == 404


def test_create_for_customer_of_another_shop(client, customer):
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    response = client.post(
        f"/shops/{other['id']}/customers/{customer['id']}/transactions",
        json={"type": "credit", "amount": 10},
    )
    assert response.status_code == 404


# --- list with running balance ----------------------------------------------


def test_list_with_running_balance(client, customer, txn_url):
    now = datetime.now(UTC)
    # Added out of order on purpose; the ledger is sorted by date.
    client.post(txn_url, json={"type": "payment", "amount": 200, "created_at": iso(now - timedelta(days=1))})
    client.post(txn_url, json={"type": "credit", "amount": 500, "created_at": iso(now - timedelta(days=5))})
    client.post(txn_url, json={"type": "credit", "amount": 100})

    response = client.get(txn_url)
    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["id"] == customer["id"]
    assert body["customer"]["balance"] == 400
    rows = [(t["type"], t["amount"], t["running_balance"]) for t in body["transactions"]]
    assert rows == [("credit", 500, 500), ("payment", 200, 300), ("credit", 100, 400)]


def test_list_empty(client, txn_url):
    body = client.get(txn_url).json()
    assert body["transactions"] == []
    assert body["customer"]["balance"] == 0


def test_list_only_shows_that_customers_transactions(client, make_customer, add_txn, customer, txn_url):
    other = make_customer("Karim")
    add_txn(other["id"], "credit", 999)
    add_txn(customer["id"], "credit", 1)
    assert [t["amount"] for t in client.get(txn_url).json()["transactions"]] == [1]


def test_list_for_missing_customer(client, shop):
    assert client.get(f"/shops/{shop['id']}/customers/999/transactions").status_code == 404


# --- get / edit / delete ----------------------------------------------------


def test_get_transaction(client, shop, customer, add_txn):
    txn = add_txn(customer["id"], "credit", 75, item="tel")
    response = client.get(f"/shops/{shop['id']}/transactions/{txn['id']}")
    assert response.status_code == 200
    assert response.json() == txn


def test_edit_amount_and_type(client, shop, customer, add_txn):
    add_txn(customer["id"], "credit", 500)
    txn = add_txn(customer["id"], "credit", 100)
    url = f"/shops/{shop['id']}/transactions/{txn['id']}"

    response = client.patch(url, json={"amount": 150})
    assert response.status_code == 200
    assert response.json()["amount"] == 150
    assert response.json()["type"] == "credit"
    assert response.json()["customer_balance"] == 650

    response = client.patch(url, json={"type": "payment"})
    assert response.json()["type"] == "payment"
    assert response.json()["amount"] == 150
    assert response.json()["customer_balance"] == 350


def test_edit_text_fields_and_clear_item(client, shop, customer, add_txn):
    txn = add_txn(customer["id"], "credit", 100, item="sugar", raw_text="old")
    url = f"/shops/{shop['id']}/transactions/{txn['id']}"
    response = client.patch(url, json={"item": None, "raw_text": "new text"})
    assert response.status_code == 200
    assert response.json()["item"] is None
    assert response.json()["raw_text"] == "new text"
    assert response.json()["created_at"] == txn["created_at"]


def test_edit_date(client, shop, customer, add_txn):
    txn = add_txn(customer["id"], "credit", 100)
    when = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    response = client.patch(
        f"/shops/{shop['id']}/transactions/{txn['id']}", json={"created_at": iso(when)}
    )
    assert datetime.fromisoformat(response.json()["created_at"]) == when


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({}, None, "Provide at least one field to update"),
        ({"amount": None}, None, "amount cannot be null"),
        ({"type": None}, None, "type cannot be null"),
        ({"amount": 0}, "amount", "Amount must be greater than 0"),
        ({"type": "gift"}, "type", None),
    ],
)
def test_edit_validation(client, shop, customer, add_txn, payload, field, message):
    txn = add_txn(customer["id"], "credit", 100)
    response = client.patch(f"/shops/{shop['id']}/transactions/{txn['id']}", json=payload)
    assert response.status_code == 422
    errors = error_messages(response)
    assert field in errors
    if message:
        assert errors[field] == message


def test_edit_missing_transaction(client, shop):
    response = client.patch(f"/shops/{shop['id']}/transactions/999", json={"amount": 5})
    assert response.status_code == 404
    assert response.json()["detail"] == f"Transaction 999 not found in shop {shop['id']}"


def test_delete_transaction(client, shop, customer, add_txn):
    keep = add_txn(customer["id"], "credit", 100)
    txn = add_txn(customer["id"], "credit", 40)
    url = f"/shops/{shop['id']}/transactions/{txn['id']}"

    response = client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    ids = [t["id"] for t in client.get(f"/shops/{shop['id']}/customers/{customer['id']}/transactions").json()["transactions"]]
    assert ids == [keep["id"]]


def test_cannot_touch_transaction_through_another_shop(client, customer, add_txn):
    txn = add_txn(customer["id"], "credit", 100)
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    url = f"/shops/{other['id']}/transactions/{txn['id']}"
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"amount": 1}).status_code == 404
    assert client.delete(url).status_code == 404


# --- Recent transactions (whole shop) ------------------------------------------------------


def test_recent_transactions_newest_first_with_customer_name(client, shop, make_customer, add_txn):
    rahim = make_customer("Rahim", note="Bazar road")
    salma = make_customer("Salma")
    now = datetime.now(UTC)
    add_txn(rahim["id"], "credit", 100, created_at=(now - timedelta(days=2)).isoformat())
    yesterday = (now - timedelta(days=1)).isoformat()
    add_txn(salma["id"], "credit", 200, item="dal", created_at=yesterday)
    add_txn(rahim["id"], "payment", 50)

    response = client.get(f"/shops/{shop['id']}/transactions")

    assert response.status_code == 200
    body = response.json()
    assert [(t["customer_name"], t["amount"]) for t in body] == [
        ("Rahim", 50),
        ("Salma", 200),
        ("Rahim", 100),
    ]
    assert body[0]["customer_note"] == "Bazar road"
    assert body[1]["item"] == "dal"


def test_recent_transactions_limit(client, shop, customer, add_txn):
    for amount in range(1, 13):
        add_txn(customer["id"], "credit", amount)
    url = f"/shops/{shop['id']}/transactions"
    assert len(client.get(url).json()) == 10  # default
    assert [t["amount"] for t in client.get(url, params={"limit": 3}).json()] == [12, 11, 10]
    assert client.get(url, params={"limit": 0}).status_code == 422
    assert client.get(url, params={"limit": 101}).status_code == 422


def test_recent_transactions_only_this_shop(client, shop, customer, add_txn):
    add_txn(customer["id"], "credit", 100)
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    assert client.get(f"/shops/{other['id']}/transactions").json() == []
    assert client.get("/shops/999/transactions").status_code == 404
