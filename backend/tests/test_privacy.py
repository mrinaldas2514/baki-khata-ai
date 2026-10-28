"""Privacy: with AI off nothing goes to the AI, the CSV export, and logs without personal data."""

import csv
import io
import logging
from datetime import UTC, datetime

import pytest

from app.logging_privacy import DropQueryString
from tests.conftest import FakeLLM, FakeSTT

# --- AI off -------------------------------------------------------------------------------


@pytest.fixture
def ai_off(client):
    assert client.patch("/auth/me", json={"ai_enabled": False}).status_code == 200


def test_ai_off_parse_uses_the_rule_based_parser_and_never_the_llm(
    client, shop, ai_off, fake_llm: FakeLLM, make_customer
):
    make_customer("Salma")
    response = client.post(f"/shops/{shop['id']}/parse", json={"text": "salma apa 500 taka baki"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"]["amount"] == 500
    assert body["parsed"]["type"] == "credit"
    assert body["match"]["status"] == "exact"
    assert fake_llm.calls == []  # nothing went to the AI provider


def test_ai_off_reminder_is_the_template_without_the_llm(
    client, shop, ai_off, fake_llm: FakeLLM, customer, add_txn
):
    add_txn(customer["id"], "credit", 300)
    response = client.post(f"/shops/{shop['id']}/customers/{customer['id']}/reminder", json={})
    assert response.status_code == 200
    assert response.json()["polished"] is False
    assert fake_llm.calls == []


def test_ai_off_voice_is_not_sent_to_the_server(client, ai_off, fake_stt: FakeSTT):
    status = client.get("/transcribe/status").json()
    response = client.post(
        "/transcribe",
        files={"file": ("voice.webm", b"audio", "audio/webm")},
        data={"language": "bn-BD"},
    )
    assert status["available"] is False
    assert response.status_code == 403
    assert "AI is turned off" in response.json()["detail"]
    assert fake_stt.calls == []


def test_ai_back_on_uses_the_llm_again(client, shop, fake_llm: FakeLLM):
    client.patch("/auth/me", json={"ai_enabled": False})
    client.patch("/auth/me", json={"ai_enabled": True})
    fake_llm.reply(
        {"customer_name": "karim", "amount": 50, "type": "payment", "item": None, "confidence": 0.9}
    )
    client.post(f"/shops/{shop['id']}/parse", json={"text": "karim 50 dilo"})
    assert len(fake_llm.calls) == 1


# --- CSV export ---------------------------------------------------------------------------


def read_csv(response) -> list[dict]:
    assert response.content.startswith("﻿".encode())  # UTF-8 BOM for Excel
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_export_csv_has_every_customer_and_transaction_with_bangla_intact(
    client, shop, make_customer, add_txn
):
    ayesha = make_customer("আয়েশা", phone="01811-000002", note="বাজার রোড")
    add_txn(
        ayesha["id"],
        "credit",
        750,
        item="চাল",
        raw_text="আয়েশা আপা ৭৫০ টাকার চাল নিলো",
        created_at=datetime(2026, 10, 20, 4, 30, tzinfo=UTC).isoformat(),
    )
    add_txn(
        ayesha["id"],
        "payment",
        250,
        raw_text="ayesha 250 dilo",
        created_at=datetime(2026, 10, 21, 4, 30, tzinfo=UTC).isoformat(),
    )
    make_customer("Babul")  # no transactions yet

    response = client.get(f"/shops/{shop['id']}/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"].startswith('attachment; filename="baki-khata-')
    rows = read_csv(response)
    assert list(rows[0]) == [
        "customer_id", "customer_name", "phone", "area_note", "date", "type", "amount", "item",
        "original_sentence", "balance_after",
    ]  # fmt: skip
    # Sorted by name: Babul, then আয়েশা (oldest first).
    assert rows[0]["customer_name"] == "Babul"
    assert rows[0]["date"] == rows[0]["amount"] == ""
    first, second = rows[1], rows[2]
    assert first["customer_name"] == "আয়েশা"
    assert first["phone"] == "+8801811000002"
    assert first["area_note"] == "বাজার রোড"
    assert first["date"] == "2026-10-20 10:30"  # shop's local time (Asia/Dhaka)
    assert (first["type"], first["amount"], first["item"]) == ("Baki", "750", "চাল")
    assert first["original_sentence"] == "আয়েশা আপা ৭৫০ টাকার চাল নিলো"
    assert first["balance_after"] == "750"
    assert (second["type"], second["amount"], second["balance_after"]) == ("Joma", "250", "500")


def test_export_neutralizes_spreadsheet_formulas(client, shop, make_customer, add_txn):
    sneaky = make_customer('=HYPERLINK("http://evil")')
    add_txn(sneaky["id"], "credit", 10, item="+cmd", raw_text="@SUM(A1)")
    row = read_csv(client.get(f"/shops/{shop['id']}/export.csv"))[0]
    assert row["customer_name"].startswith("'=")
    assert row["item"] == "'+cmd"
    assert row["original_sentence"] == "'@SUM(A1)"


def test_export_of_an_empty_shop_is_just_the_header(client, shop):
    assert read_csv(client.get(f"/shops/{shop['id']}/export.csv")) == []


# --- Logs ---------------------------------------------------------------------------------


def test_logs_carry_ids_not_names_sentences_or_amounts(client, shop, fake_llm: FakeLLM, caplog):
    caplog.set_level(logging.DEBUG)
    sentence = "Zubaida apa 4321 taka baki, dal r tel"
    # A broken first answer goes down the retry path, which used to log the answer.
    fake_llm.reply(
        '{"customer_name": "Zubaida", "amount": "4321"}',
        {
            "customer_name": "Zubaida",
            "amount": 4321,
            "type": "credit",
            "item": "dal, tel",
            "confidence": 0.9,
        },
    )
    preview = client.post(f"/shops/{shop['id']}/parse", json={"text": sentence}).json()
    client.post(
        f"/shops/{shop['id']}/parse/confirm",
        json={"raw_text": sentence, "type": "credit", "amount": 4321, "item": "dal, tel",
              "new_customer": {"name": preview["match"]["suggested_name"], "phone": "01712345678"}},
    )  # fmt: skip
    customer = client.get(f"/shops/{shop['id']}/customers").json()[0]
    fake_llm.reply('{"message": "not json')  # reminder polish fails
    client.post(f"/shops/{shop['id']}/customers/{customer['id']}/reminder", json={})

    logged = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert logged, "expected some log lines (ids only)"
    text = "\n".join(r.getMessage() for r in logged)
    for secret in ("Zubaida", "4321", "dal", "01712345678", "1712345678"):
        assert secret not in text


def test_access_log_drops_query_strings():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", "/shops/1/customers?search=rahim", "1.1", 200), None,
    )  # fmt: skip
    DropQueryString().filter(record)
    assert record.getMessage() == '1.2.3.4:5 - "GET /shops/1/customers HTTP/1.1" 200'
