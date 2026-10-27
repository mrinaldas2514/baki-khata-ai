from tests.conftest import error_messages


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_shop(client):
    response = client.post("/shops", json={"name": "  Karim Store ", "owner_name": "Karim"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Karim Store"  # whitespace trimmed
    assert body["owner_name"] == "Karim"
    assert body["id"] > 0
    assert body["created_at"]


def test_create_shop_requires_names(client):
    response = client.post("/shops", json={"name": "   "})
    assert response.status_code == 422
    errors = error_messages(response)
    assert "name" in errors
    assert errors["owner_name"] == "Field required"


def test_get_shop(client, shop):
    response = client.get(f"/shops/{shop['id']}")
    assert response.status_code == 200
    assert response.json() == shop


def test_get_missing_shop(client):
    response = client.get("/shops/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Shop 999 not found"}
