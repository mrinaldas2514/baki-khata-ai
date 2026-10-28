"""GET /shops/{id}. Shops are created by POST /auth/register (see test_auth.py)."""


def test_health(anon_client):
    assert anon_client.get("/health").json() == {"status": "ok"}


def test_get_shop(client, shop):
    response = client.get(f"/shops/{shop['id']}")
    assert response.status_code == 200
    assert response.json() == shop
    assert shop["name"] == "Karim Store"
    assert shop["owner_name"] == "Karim"


def test_get_missing_shop(client):
    response = client.get("/shops/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Shop 999 not found"}


def test_there_is_no_open_create_shop_endpoint(anon_client):
    response = anon_client.post("/shops", json={"name": "Shop", "owner_name": "Owner"})
    assert response.status_code == 404
