from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import error_messages


def test_create_customer(client, shop):
    response = client.post(
        f"/shops/{shop['id']}/customers",
        json={"name": "Rahim", "phone": "+880 1711-000000", "note": "Bazar road"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["shop_id"] == shop["id"]
    assert body["name"] == "Rahim"
    assert body["phone"] == "+8801711000000"  # stored normalized
    assert body["note"] == "Bazar road"
    assert body["balance"] == 0


def test_phone_and_note_are_optional_and_blank_becomes_null(client, shop):
    response = client.post(
        f"/shops/{shop['id']}/customers", json={"name": "Karim", "phone": " ", "note": ""}
    )
    assert response.status_code == 201
    assert response.json()["phone"] is None
    assert response.json()["note"] is None


def test_customer_validation(client, shop):
    response = client.post(
        f"/shops/{shop['id']}/customers", json={"name": "", "phone": "call me", "note": "x" * 201}
    )
    assert response.status_code == 422
    errors = error_messages(response)
    assert set(errors) == {"name", "phone", "note"}
    assert "digits" in errors["phone"]


def test_create_customer_in_missing_shop(client):
    response = client.post("/shops/999/customers", json={"name": "Rahim"})
    assert response.status_code == 404


def test_duplicate_name_without_note_is_rejected(client, make_customer, shop):
    make_customer("Rahim")
    response = client.post(f"/shops/{shop['id']}/customers", json={"name": "rahim"})
    assert response.status_code == 409
    assert "area/note" in response.json()["detail"]


def test_same_name_with_different_notes_is_allowed(make_customer):
    a = make_customer("Rahim", note="Bazar road")
    b = make_customer("Rahim", note="Tea stall")
    c = make_customer("Rahim")
    assert len({a["id"], b["id"], c["id"]}) == 3


def test_duplicate_name_and_note_is_rejected(client, make_customer, shop):
    make_customer("Rahim", note="Bazar road")
    response = client.post(
        f"/shops/{shop['id']}/customers", json={"name": "Rahim", "note": "bazar ROAD"}
    )
    assert response.status_code == 409


def test_same_name_in_another_shop_is_allowed(client, make_customer, other_shop):
    make_customer("Rahim")
    other = other_shop
    response = client.post(
        f"/shops/{other['id']}/customers", json={"name": "Rahim"}, headers=other["headers"]
    )
    assert response.status_code == 201


def test_list_customers_with_balances(client, shop, make_customer, add_txn, other_shop):
    rahim = make_customer("Rahim")
    karim = make_customer("karim")
    make_customer("Babul")
    add_txn(rahim["id"], "credit", 500)
    add_txn(rahim["id"], "payment", 100)
    add_txn(karim["id"], "credit", 50)

    other = other_shop
    client.post(
        f"/shops/{other['id']}/customers", json={"name": "Outsider"}, headers=other["headers"]
    )

    response = client.get(f"/shops/{shop['id']}/customers")
    assert response.status_code == 200
    rows = [(c["name"], c["balance"]) for c in response.json()]
    assert rows == [("Babul", 0), ("karim", 50), ("Rahim", 400)]  # sorted by name


def test_search_customers(client, shop, make_customer):
    make_customer("Rahim", note="Bazar road")
    make_customer("Karim", phone="01999999999")
    make_customer("Salma", note="Near mosque")

    def names(term):
        resp = client.get(f"/shops/{shop['id']}/customers", params={"search": term})
        return [c["name"] for c in resp.json()]

    assert names("RAH") == ["Rahim"]
    assert names("bazar") == ["Rahim"]
    assert names("0199") == ["Karim"]
    assert names("%") == []  # wildcards are treated literally


def test_list_customers_for_missing_shop(client):
    assert client.get("/shops/999/customers").status_code == 404


def test_get_customer_with_balance(client, shop, customer, add_txn):
    add_txn(customer["id"], "credit", 300)
    add_txn(customer["id"], "payment", 120)
    response = client.get(f"/shops/{shop['id']}/customers/{customer['id']}")
    assert response.status_code == 200
    assert response.json()["balance"] == 180
    assert response.json()["name"] == "Rahim"


def test_get_missing_customer(client, shop):
    response = client.get(f"/shops/{shop['id']}/customers/999")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Customer 999 not found in shop {shop['id']}"


def test_cannot_read_customer_through_another_shop(client, customer, other_shop):
    other = other_shop
    assert client.get(f"/shops/{other['id']}/customers/{customer['id']}").status_code == 404


def test_list_shows_how_old_each_baki_is(client, shop, make_customer, add_txn):
    now = datetime.now(UTC)
    old = make_customer("Old")
    add_txn(old["id"], "credit", 100, created_at=(now - timedelta(days=40)).isoformat())
    add_txn(old["id"], "credit", 50, created_at=(now - timedelta(days=5)).isoformat())
    add_txn(old["id"], "payment", 100)  # pays off the 40-day-old credit first
    settled = make_customer("Settled")
    add_txn(settled["id"], "credit", 70)
    add_txn(settled["id"], "payment", 70)
    make_customer("Nothing yet")

    listed = {c["name"]: c for c in client.get(f"/shops/{shop['id']}/customers").json()}
    owed_since = datetime.fromisoformat(listed["Old"]["owed_since"])
    assert abs(owed_since - (now - timedelta(days=5))) < timedelta(seconds=5)
    assert listed["Old"]["balance"] == 50
    assert listed["Settled"]["owed_since"] is None
    assert listed["Nothing yet"]["owed_since"] is None


# --- Edit and delete ----------------------------------------------------------------------


def test_edit_name_phone_and_note(client, shop, customer):
    url = f"/shops/{shop['id']}/customers/{customer['id']}"
    response = client.patch(
        url, json={"name": "Rahim Uddin", "phone": "+91 98765 43210", "note": "Haat"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["phone"], body["note"]) == ("Rahim Uddin", "+919876543210", "Haat")
    assert client.get(url).json()["phone"] == "+919876543210"


def test_edit_only_what_is_sent_and_clear_with_null(client, shop, customer, add_txn):
    add_txn(customer["id"], "credit", 200)
    url = f"/shops/{shop['id']}/customers/{customer['id']}"
    body = client.patch(url, json={"phone": None}).json()
    assert body["phone"] is None
    assert body["name"] == "Rahim"
    assert body["note"] == "Bazar road"
    assert body["balance"] == 200


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"phone": "12345"}, "phone", "Bangladesh mobile number"),
        ({"phone": "01211000001"}, "phone", "Bangladesh mobile number"),
        ({"name": None}, None, "name cannot be null"),
        ({"name": "  "}, "name", "at least 1 character"),
        ({}, None, "at least one field"),
    ],
)
def test_edit_validation(client, shop, customer, payload, field, message):
    response = client.patch(f"/shops/{shop['id']}/customers/{customer['id']}", json=payload)
    assert response.status_code == 422
    assert message in error_messages(response)[field]


def test_edit_into_a_duplicate_is_409(client, shop, make_customer):
    make_customer("Rahim", note="Tea stall")
    other = make_customer("Rahim", note="Bazar road")
    url = f"/shops/{shop['id']}/customers/{other['id']}"
    assert client.patch(url, json={"note": "tea stall"}).status_code == 409
    # Saving its own name and note again is fine.
    assert client.patch(url, json={"name": "Rahim", "note": "Bazar road"}).status_code == 200


def test_delete_customer_only_without_entries(client, shop, customer, make_customer, add_txn):
    add_txn(customer["id"], "credit", 100)
    assert client.delete(f"/shops/{shop['id']}/customers/{customer['id']}").status_code == 409
    empty = make_customer("Nobody")
    assert client.delete(f"/shops/{shop['id']}/customers/{empty['id']}").status_code == 204
    assert client.get(f"/shops/{shop['id']}/customers/{empty['id']}").status_code == 404
