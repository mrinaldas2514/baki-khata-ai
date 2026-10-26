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
    assert body["phone"] == "+880 1711-000000"
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


def test_same_name_in_another_shop_is_allowed(client, make_customer):
    make_customer("Rahim")
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    response = client.post(f"/shops/{other['id']}/customers", json={"name": "Rahim"})
    assert response.status_code == 201


def test_list_customers_with_balances(client, shop, make_customer, add_txn):
    rahim = make_customer("Rahim")
    karim = make_customer("karim")
    make_customer("Babul")
    add_txn(rahim["id"], "credit", 500)
    add_txn(rahim["id"], "payment", 100)
    add_txn(karim["id"], "credit", 50)

    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    client.post(f"/shops/{other['id']}/customers", json={"name": "Outsider"})

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


def test_cannot_read_customer_through_another_shop(client, customer):
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    assert client.get(f"/shops/{other['id']}/customers/{customer['id']}").status_code == 404
