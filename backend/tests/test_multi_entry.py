"""Several customers in one sentence: "rahim 200 baki, karim 500 dilo, salma 100 baki"."""

import pytest
from sqlalchemy import func, select

from app.llm.rule_based import parse_text
from app.models import Customer, Transaction
from app.services.parsing import parse_entries_with_llm
from tests.conftest import FakeLLM

SENTENCE = "rahim 200 baki, karim 500 dilo, salma 100 baki"


def entry(name, amount, type_="credit", item=None, confidence=0.9):
    return {
        "customer_name": name,
        "amount": amount,
        "type": type_,
        "item": item,
        "confidence": confidence,
    }


THREE = {"entries": [entry("rahim", 200), entry("karim", 500, "payment"), entry("salma", 100)]}


def test_preview_has_one_card_per_customer(client, shop, fake_llm: FakeLLM, make_customer):
    rahim = make_customer("Rahim")
    make_customer("Karim")
    fake_llm.reply(THREE)

    response = client.post(f"/shops/{shop['id']}/parse", json={"text": SENTENCE})

    assert response.status_code == 200, response.text
    body = response.json()
    entries = body["entries"]
    assert [e["parsed"]["customer_name"] for e in entries] == ["rahim", "karim", "salma"]
    assert [e["parsed"]["amount"] for e in entries] == [200, 500, 100]
    assert [e["parsed"]["type"] for e in entries] == ["credit", "payment", "credit"]
    assert [e["match"]["status"] for e in entries] == ["exact", "exact", "new"]
    assert entries[0]["match"]["customer"]["id"] == rahim["id"]
    # The top-level fields are the first entry, as before.
    assert body["parsed"] == entries[0]["parsed"]
    assert body["match"] == entries[0]["match"]
    assert len(fake_llm.calls) == 1


def test_a_usual_sentence_is_one_entry(client, shop, fake_llm: FakeLLM):
    fake_llm.reply({"entries": [entry("salma", 500, item="dal, tel")]})
    body = client.post(
        f"/shops/{shop['id']}/parse", json={"text": "salma apa pach sho taka baki, dal r tel"}
    ).json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["parsed"] == body["parsed"]


def test_each_entrys_amount_is_checked_against_the_sentence(client, shop, fake_llm: FakeLLM):
    fake_llm.reply({"entries": [entry("rahim", 200), entry("karim", 900, "payment")]})
    body = client.post(f"/shops/{shop['id']}/parse", json={"text": SENTENCE}).json()
    assert body["entries"][0]["warnings"] == []
    assert "900" in body["entries"][1]["warnings"][0]
    assert body["entries"][1]["parsed"]["confidence"] == 0.5


def test_a_bad_entry_is_retried_with_its_position(fake_llm: FakeLLM):
    fake_llm.reply({"entries": [entry("rahim", 200), {"customer_name": "karim"}]}, THREE)
    parsed = parse_entries_with_llm(fake_llm, SENTENCE)
    assert len(parsed) == 3
    assert "entries.1: amount: Field required" in fake_llm.calls[1][3]["content"]


@pytest.mark.parametrize("entries", [[], [entry("a", 1)] * 11, "rahim"])
def test_entries_must_be_a_short_list(fake_llm: FakeLLM, entries):
    fake_llm.reply({"entries": entries}, THREE)
    parse_entries_with_llm(fake_llm, SENTENCE)
    assert "entries must be a list of 1 to 10" in fake_llm.calls[1][3]["content"]


# --- Without AI: the rule-based parser splits too ------------------------------------------


def test_rule_based_parser_splits_whole_entries_only():
    assert parse_text(SENTENCE) == {
        "entries": [
            entry("rahim", 200, confidence=0.8),
            entry("karim", 500, "payment", confidence=0.8),
            entry("salma", 100, confidence=0.8),
        ]
    }
    # The part after the comma is goods, not another customer: one entry.
    single = parse_text("salma apa pach sho taka baki, dal r tel")
    assert (single["customer_name"], single["amount"], single["item"]) == ("salma", 500, "dal, tel")
    # A thousands separator is not a split.
    assert parse_text("Abul 2,500 tk jama")["amount"] == 2500


def test_ai_off_multi_entry_never_calls_the_llm(client, shop, fake_llm: FakeLLM):
    client.patch("/auth/me", json={"ai_enabled": False})
    body = client.post(f"/shops/{shop['id']}/parse", json={"text": SENTENCE}).json()
    assert [e["parsed"]["customer_name"] for e in body["entries"]] == ["rahim", "karim", "salma"]
    assert fake_llm.calls == []


# --- Save all ------------------------------------------------------------------------------


def confirm(**fields):
    return {"raw_text": SENTENCE, "type": "credit", "item": None, **fields}


def test_confirm_many_saves_every_entry_in_order(client, shop, make_customer, add_txn, db):
    rahim = make_customer("Rahim")
    add_txn(rahim["id"], "credit", 50)
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={
            "entries": [
                confirm(amount=200, customer_id=rahim["id"]),
                confirm(amount=500, type="payment", new_customer={"name": "Karim"}),
                confirm(amount=100, new_customer={"name": "Salma", "phone": "01811000002"}),
            ]
        },
    )
    assert response.status_code == 201, response.text
    results = response.json()["results"]
    assert [r["customer"]["name"] for r in results] == ["Rahim", "Karim", "Salma"]
    assert [r["customer_created"] for r in results] == [False, True, True]
    assert [r["customer"]["balance"] for r in results] == [250, -500, 100]
    assert [r["transaction"]["raw_text"] for r in results] == [SENTENCE] * 3
    assert results[2]["customer"]["phone"] == "+8801811000002"
    assert db.scalar(select(func.count()).select_from(Transaction)) == 4


def test_the_same_new_customer_twice_is_created_once(client, shop, db):
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={
            "entries": [
                confirm(amount=50, new_customer={"name": "Tanvir"}),
                confirm(amount=20, type="payment", new_customer={"name": "tanvir"}),
            ]
        },
    )
    assert response.status_code == 201, response.text
    results = response.json()["results"]
    assert results[0]["customer"]["id"] == results[1]["customer"]["id"]
    assert [r["customer_created"] for r in results] == [True, False]
    assert results[1]["customer"]["balance"] == 30
    assert db.scalar(select(func.count()).select_from(Customer)) == 1


def test_confirm_many_is_all_or_nothing(client, shop, other_shop, db):
    outsider = client.post(
        f"/shops/{other_shop['id']}/customers",
        json={"name": "Outsider"},
        headers=other_shop["headers"],
    ).json()
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={
            "entries": [
                confirm(amount=50, new_customer={"name": "Tanvir"}),
                confirm(amount=20, customer_id=outsider["id"]),  # another shop's customer
            ]
        },
    )
    assert response.status_code == 404
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Transaction)) == 0
    assert [c.name for c in db.scalars(select(Customer))] == ["Outsider"]


@pytest.mark.parametrize("count", [0, 11])
def test_confirm_many_takes_1_to_10_entries(client, shop, count):
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={"entries": [confirm(amount=5, new_customer={"name": f"C{i}"}) for i in range(count)]},
    )
    assert response.status_code == 422
