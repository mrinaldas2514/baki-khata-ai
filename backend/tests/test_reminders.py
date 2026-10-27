"""POST /shops/{id}/customers/{id}/reminder: the Banglish baki reminder for WhatsApp."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LLMProviderError
from app.main import create_app
from app.services.reminders import format_amount, whatsapp_number


@pytest.fixture
def rahim(customer, add_txn):
    # Customer "Rahim" (Bazar road, 01711-000000) in "Karim Store" owned by "Karim".
    add_txn(customer["id"], "credit", 1000, created_at=datetime(2026, 9, 12, 6, 0, tzinfo=UTC).isoformat())
    add_txn(customer["id"], "credit", 500)
    add_txn(customer["id"], "payment", 300)
    return customer


def remind(client, shop, customer, **body):
    return client.post(f"/shops/{shop['id']}/customers/{customer['id']}/reminder", json=body or None)


def test_template_reminder_has_name_amount_date_and_shop(client, shop, rahim, fake_llm):
    response = remind(client, shop, rahim, polish=False)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == (
        "Priyo Rahim,\n"
        "Ashakori bhalo achen. Karim Store-e apnar 1,200 taka baki ache (12 September theke).\n"
        "Shubidha moto shodh kore dile khub upokar hoy.\n"
        "Dhonnobad,\n"
        "Karim, Karim Store"
    )
    assert body["polished"] is False
    assert body["phone"] == "01711-000000"
    assert body["whatsapp_number"] == "8801711000000"
    assert fake_llm.calls == []


def test_reminder_uses_the_ai_wording_when_it_keeps_the_facts(client, shop, rahim, fake_llm):
    polished = (
        "Rahim bhai, kemon achen? Karim Store-e apnar 1,200 taka baki ache (12 September theke). "
        "Shomoy pele ektu shodh kore diben. Dhonnobad! - Karim"
    )
    fake_llm.reply({"message": polished})

    body = remind(client, shop, rahim).json()

    assert body == {**body, "message": polished, "polished": True}
    # The model is given the template to reword, with rules to keep the name and amount.
    system, user = fake_llm.calls[0]
    assert "Keep the amount exactly" in system["content"]
    assert "1,200 taka" in user["content"]


@pytest.mark.parametrize(
    "answer",
    [
        {"message": "Rahim bhai, apnar 2,000 taka baki ache. Dhonnobad, Karim Store"},  # wrong amount
        {"message": "Rahim bhai, 1,200 taka baki, 7 diner moddhe din. Karim Store"},  # new number
        {"message": "Bhai, apnar 1,200 taka baki ache. Dhonnobad, Karim Store"},  # name dropped
        {"message": "short"},
        {"text": "wrong key"},
        "not json",
        LLMProviderError("timeout"),
    ],
)
def test_reminder_falls_back_to_the_template(client, shop, rahim, fake_llm, answer):
    fake_llm.reply(answer)
    body = remind(client, shop, rahim).json()
    assert body["polished"] is False
    assert body["message"].startswith("Priyo Rahim,\n")
    assert "1,200 taka baki" in body["message"]


def test_reminder_without_phone_can_still_be_copied(client, shop, make_customer, add_txn):
    salma = make_customer("Salma")
    add_txn(salma["id"], "credit", 250)
    body = remind(client, shop, salma, polish=False).json()
    assert body["phone"] is None
    assert body["whatsapp_number"] is None
    assert "Priyo Salma" in body["message"]
    assert "250 taka baki ache (" in body["message"]


def test_no_reminder_without_baki(client, shop, customer, add_txn):
    assert remind(client, shop, customer).status_code == 409
    add_txn(customer["id"], "payment", 100)  # paid in advance
    response = remind(client, shop, customer)
    assert response.status_code == 409
    assert "no baki" in response.json()["detail"]


def test_reminder_for_missing_or_other_shops_customer(client, shop, rahim):
    assert client.post(f"/shops/{shop['id']}/customers/999/reminder").status_code == 404
    other = client.post("/shops", json={"name": "Other", "owner_name": "X"}).json()
    assert client.post(f"/shops/{other['id']}/customers/{rahim['id']}/reminder").status_code == 404


def test_demo_parser_does_not_reword_reminders(engine, monkeypatch, shop, rahim):
    """With only the rule-based parser (no API key) the template is used as is."""
    monkeypatch.setattr("app.llm.get_settings", lambda: Settings(_env_file=None, llm_provider="fake"))
    with TestClient(create_app(engine)) as client:
        body = remind(client, shop, rahim).json()
    assert body["polished"] is False
    assert body["message"].startswith("Priyo Rahim,")


def test_whatsapp_number_uses_the_configured_country_code(engine, monkeypatch, shop, rahim):
    settings = Settings(_env_file=None, phone_country_code="91")
    monkeypatch.setattr("app.routers.customers.get_settings", lambda: settings)
    with TestClient(create_app(engine)) as client:
        assert remind(client, shop, rahim, polish=False).json()["whatsapp_number"] == "911711000000"


@pytest.mark.parametrize(
    ("phone", "number"),
    [
        ("01711-000001", "8801711000001"),
        ("1711 000001", "8801711000001"),
        ("+880 1711-000001", "8801711000001"),
        ("8801711000001", "8801711000001"),
        ("+91 98765 43210", "919876543210"),
        ("0091 98765 43210", "919876543210"),
        ("12345", None),
        ("", None),
        (None, None),
    ],
)
def test_whatsapp_number(phone, number):
    assert whatsapp_number(phone, "880") == number


@pytest.mark.parametrize(
    ("amount", "text"),
    [(5, "5"), (999, "999"), (1200, "1,200"), (125000, "1,25,000"), (10_000_000, "1,00,00,000")],
)
def test_format_amount_uses_south_asian_grouping(amount, text):
    assert format_amount(amount) == text
