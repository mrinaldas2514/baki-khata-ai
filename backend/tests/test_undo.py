"""Undo right after saving: delete the entry, and the customer it created if it has no others."""


def save_new_customer_entry(client, shop, name="Tanvir"):
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm",
        json={
            "raw_text": f"{name} 90 taka baki",
            "type": "credit",
            "amount": 90,
            "new_customer": {"name": name},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_undo_removes_the_entry_and_the_customer_it_created(client, shop):
    saved = save_new_customer_entry(client, shop)
    txn_id, customer_id = saved["transaction"]["id"], saved["customer"]["id"]

    assert client.delete(f"/shops/{shop['id']}/transactions/{txn_id}").status_code == 204
    assert client.delete(f"/shops/{shop['id']}/customers/{customer_id}").status_code == 204

    assert client.get(f"/shops/{shop['id']}/customers").json() == []
    assert client.get(f"/shops/{shop['id']}/transactions").json() == []


def test_undo_keeps_a_customer_who_got_another_entry_meanwhile(client, shop, add_txn):
    saved = save_new_customer_entry(client, shop)
    customer_id = saved["customer"]["id"]
    add_txn(customer_id, "payment", 40)

    client.delete(f"/shops/{shop['id']}/transactions/{saved['transaction']['id']}")
    assert client.delete(f"/shops/{shop['id']}/customers/{customer_id}").status_code == 409

    customer = client.get(f"/shops/{shop['id']}/customers/{customer_id}").json()
    assert customer["balance"] == -40


def test_undo_a_whole_multi_entry_save(client, shop, customer, add_txn):
    add_txn(customer["id"], "credit", 300)
    results = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={
            "entries": [
                {"raw_text": "x", "type": "credit", "amount": 200, "customer_id": customer["id"]},
                {"raw_text": "x", "type": "credit", "amount": 50, "new_customer": {"name": "Rupa"}},
            ]
        },
    ).json()["results"]

    for result in results:
        url = f"/shops/{shop['id']}/transactions/{result['transaction']['id']}"
        assert client.delete(url).status_code == 204
    new = [r["customer"]["id"] for r in results if r["customer_created"]]
    assert [client.delete(f"/shops/{shop['id']}/customers/{c}").status_code for c in new] == [204]

    rows = client.get(f"/shops/{shop['id']}/customers").json()
    assert [(c["name"], c["balance"]) for c in rows] == [("Rahim", 300)]
