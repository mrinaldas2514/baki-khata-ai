"""POST /shops/{id}/parse (preview, saves nothing) and /parse/confirm (saves)."""

import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import FakeLLM, error_messages


@pytest.fixture
def parse_url(shop):
    return f"/shops/{shop['id']}/parse"


def llm_answer(name="rahim", amount=120, type_="credit", item="2 kg chal", confidence=0.95):
    return {
        "customer_name": name,
        "amount": amount,
        "type": type_,
        "item": item,
        "confidence": confidence,
    }


def transaction_count(client, shop) -> int:
    customers = client.get(f"/shops/{shop['id']}/customers").json()
    return sum(
        len(
            client.get(f"/shops/{shop['id']}/customers/{c['id']}/transactions").json()[
                "transactions"
            ]
        )
        for c in customers
    )


# --- Preview ------------------------------------------------------------------------------


def test_preview_matches_existing_customer_and_saves_nothing(
    client, shop, parse_url, fake_llm: FakeLLM, make_customer, add_txn
):
    rahim = make_customer("Rahim")
    add_txn(rahim["id"], "credit", 300)
    fake_llm.reply(llm_answer())
    text = "rahim bhai 2 kg chal 120 taka baki"

    response = client.post(parse_url, json={"text": f"  {text} "})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["raw_text"] == text
    assert body["parsed"] == llm_answer()
    assert body["match"]["status"] == "exact"
    assert body["match"]["customer"]["id"] == rahim["id"]
    assert body["match"]["customer"]["balance"] == 300
    assert body["match"]["customer"]["score"] == 100
    assert body["warnings"] == []
    # Still only the one transaction added above.
    assert transaction_count(client, shop) == 1


def test_preview_fuzzy_match_warns(client, parse_url, fake_llm: FakeLLM, make_customer):
    rahim = make_customer("Rahim")
    fake_llm.reply(llm_answer(name="Rohim", amount=200, type_="payment", item=None))

    body = client.post(parse_url, json={"text": "Rohim 200 dilo"}).json()

    assert body["match"]["status"] == "fuzzy"
    assert body["match"]["customer"]["id"] == rahim["id"]
    assert body["warnings"] == ["'Rohim' was matched to Rahim. Please check it."]


def test_preview_ambiguous_lists_candidates(client, parse_url, fake_llm: FakeLLM, make_customer):
    a = make_customer("Rahim", note="Bazar road")
    b = make_customer("Rahim", note="Tea stall")
    make_customer("Salma")
    fake_llm.reply(llm_answer())

    body = client.post(parse_url, json={"text": "rahim bhai 2 kg chal 120 taka baki"}).json()

    assert body["match"]["status"] == "ambiguous"
    assert body["match"]["customer"] is None
    assert {c["id"] for c in body["match"]["candidates"]} == {a["id"], b["id"]}
    assert {c["note"] for c in body["match"]["candidates"]} == {"Bazar road", "Tea stall"}


def test_preview_new_customer(client, parse_url, fake_llm: FakeLLM, make_customer):
    make_customer("Karim")
    fake_llm.reply(llm_answer(name="salma apa", amount=500, item="dal, tel"))

    body = client.post(parse_url, json={"text": "salma apa pach sho taka baki, dal r tel"}).json()

    assert body["match"] == {
        "status": "new",
        "customer": None,
        "candidates": [],
        "suggested_name": "Salma",
    }
    assert body["warnings"] == []  # "pach sho" = 500 was found in the sentence


def test_preview_bangla_sentence(client, parse_url, fake_llm: FakeLLM, make_customer):
    rahim = make_customer("Rahim")
    fake_llm.reply(llm_answer(name="রহিম", amount=200, type_="payment", item=None))

    body = client.post(parse_url, json={"text": "রহিম ২০০ টাকা দিল"}).json()

    assert body["parsed"]["amount"] == 200
    assert body["match"]["status"] == "exact"
    assert body["match"]["customer"]["id"] == rahim["id"]


def test_preview_flags_amount_not_in_sentence(client, parse_url, fake_llm: FakeLLM):
    fake_llm.reply(llm_answer(amount=1200, confidence=0.9))

    body = client.post(parse_url, json={"text": "rahim bhai 2 kg chal 120 taka baki"}).json()

    assert body["parsed"]["confidence"] == 0.5
    assert body["warnings"] == ["The amount 1200 was not found in the sentence. Please check it."]


@pytest.mark.parametrize("text", ["", "   ", "x" * 501])
def test_preview_validates_text(client, parse_url, fake_llm: FakeLLM, text):
    response = client.post(parse_url, json={"text": text})
    assert response.status_code == 422
    assert "text" in error_messages(response)
    assert fake_llm.calls == []


def test_preview_missing_shop_does_not_call_llm(client, fake_llm: FakeLLM):
    response = client.post("/shops/999/parse", json={"text": "karim 500 dilo"})
    assert response.status_code == 404
    assert fake_llm.calls == []


def test_preview_retries_then_succeeds(client, parse_url, fake_llm: FakeLLM):
    fake_llm.reply("oops", llm_answer())
    response = client.post(parse_url, json={"text": "rahim bhai 2 kg chal 120 taka baki"})
    assert response.status_code == 200
    assert len(fake_llm.calls) == 2


def test_preview_invalid_twice_is_502(client, parse_url, fake_llm: FakeLLM):
    fake_llm.reply("oops", {"customer_name": "rahim"})
    response = client.post(parse_url, json={"text": "rahim bhai 2 kg chal 120 taka baki"})
    assert response.status_code == 502
    assert "enter the transaction manually" in response.json()["detail"]


def test_preview_not_a_transaction_is_422(client, parse_url, fake_llm: FakeLLM):
    fake_llm.reply({"error": "no amount"})
    response = client.post(parse_url, json={"text": "rina 2 ta saban"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Could not find a transaction in this sentence: no amount"}


def test_preview_provider_down_is_503_without_leaking_details(client, parse_url, fake_llm):
    from app.llm import LLMProviderError

    fake_llm.reply(LLMProviderError("401 invalid api key gsk_secret"))
    response = client.post(parse_url, json={"text": "karim 500 dilo"})
    assert response.status_code == 503
    assert "gsk_secret" not in response.text


def test_preview_with_groq_but_no_api_key_is_503(engine, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "app.llm.get_settings", lambda: Settings(_env_file=None, llm_provider="groq")
    )
    with TestClient(create_app(engine)) as client:
        shop = client.post("/shops", json={"name": "Shop", "owner_name": "Owner"}).json()
        response = client.post(f"/shops/{shop['id']}/parse", json={"text": "karim 500 dilo"})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


# --- Confirm ------------------------------------------------------------------------------


def test_confirm_existing_customer(client, shop, parse_url, customer, add_txn):
    add_txn(customer["id"], "credit", 300)
    response = client.post(
        f"{parse_url}/confirm",
        json={
            "raw_text": "rahim bhai 2 kg chal 120 taka baki",
            "type": "credit",
            "amount": 120,
            "item": "2 kg chal",
            "customer_id": customer["id"],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_created"] is False
    assert body["customer"]["id"] == customer["id"]
    assert body["customer"]["balance"] == 420
    txn = body["transaction"]
    assert txn["raw_text"] == "rahim bhai 2 kg chal 120 taka baki"
    assert txn["item"] == "2 kg chal"
    assert txn["customer_balance"] == 420

    ledger = client.get(f"/shops/{shop['id']}/customers/{customer['id']}/transactions").json()
    assert [t["raw_text"] for t in ledger["transactions"]][-1] == txn["raw_text"]


def test_confirm_new_customer(client, shop, parse_url):
    response = client.post(
        f"{parse_url}/confirm",
        json={
            "raw_text": "salma apa pach sho taka baki, dal r tel",
            "type": "credit",
            "amount": 500,
            "item": "dal, tel",
            "new_customer": {"name": "Salma", "note": "Mosque road"},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_created"] is True
    assert body["customer"]["name"] == "Salma"
    assert body["customer"]["note"] == "Mosque road"
    assert body["customer"]["balance"] == 500
    assert body["transaction"]["customer_id"] == body["customer"]["id"]

    customers = client.get(f"/shops/{shop['id']}/customers").json()
    assert [(c["name"], c["balance"]) for c in customers] == [("Salma", 500)]


def test_confirm_duplicate_new_customer_saves_nothing(client, shop, parse_url, make_customer):
    make_customer("Salma")
    response = client.post(
        f"{parse_url}/confirm",
        json={"raw_text": "salma 500 baki", "type": "credit", "amount": 500,
              "new_customer": {"name": "salma"}},
    )  # fmt: skip
    assert response.status_code == 409
    assert transaction_count(client, shop) == 0
    assert len(client.get(f"/shops/{shop['id']}/customers").json()) == 1


def test_confirm_customer_of_another_shop(client, parse_url, customer):
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    response = client.post(
        f"/shops/{other['id']}/parse/confirm",
        json={"raw_text": "rahim 50 baki", "type": "credit", "amount": 50,
              "customer_id": customer["id"]},
    )  # fmt: skip
    assert response.status_code == 404


def test_confirm_new_customer_in_missing_shop(client):
    response = client.post(
        "/shops/999/parse/confirm",
        json={"raw_text": "x 50 baki", "type": "credit", "amount": 50,
              "new_customer": {"name": "X"}},
    )  # fmt: skip
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"customer_id": 1, "new_customer": {"name": "X"}}, None, "exactly one"),
        ({}, None, "exactly one"),
        ({"customer_id": 1, "raw_text": "  "}, "raw_text", None),
        ({"customer_id": 1, "amount": 0}, "amount", "greater than 0"),
        ({"customer_id": 1, "amount": 10.5}, "amount", None),
        ({"customer_id": 1, "type": "loan"}, "type", None),
        ({"new_customer": {"name": ""}}, "new_customer.name", None),
    ],
)
def test_confirm_validation(client, parse_url, payload, field, message):
    body = {"raw_text": "rahim 120 baki", "type": "credit", "amount": 120} | payload
    response = client.post(f"{parse_url}/confirm", json=body)
    assert response.status_code == 422
    errors = error_messages(response)
    assert field in errors
    if message:
        assert message in errors[field]


def test_parse_then_confirm_flow(client, shop, parse_url, fake_llm: FakeLLM, make_customer):
    """What the app does: preview, let the shopkeeper edit, then confirm."""
    karim = make_customer("Karim")
    fake_llm.reply(llm_answer(name="karim", amount=500, type_="payment", item=None))
    preview = client.post(parse_url, json={"text": "karim 500 dilo"}).json()
    assert preview["match"]["customer"]["id"] == karim["id"]

    # The shopkeeper corrects the amount before saving.
    response = client.post(
        f"{parse_url}/confirm",
        json={
            "raw_text": preview["raw_text"],
            "type": preview["parsed"]["type"],
            "amount": 550,
            "item": preview["parsed"]["item"],
            "customer_id": preview["match"]["customer"]["id"],
        },
    )
    assert response.status_code == 201
    assert response.json()["customer"]["balance"] == -550
    assert response.json()["transaction"]["raw_text"] == "karim 500 dilo"
