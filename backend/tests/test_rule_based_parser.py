"""The rule-based demo parser used when LLM_PROVIDER=fake (or there is no Groq key)."""

import json

import pytest

from app.llm.rule_based import RuleBasedLLMClient, parse_sentence
from app.schemas import ParsedTransaction
from app.services.name_matching import clean_name
from app.services.number_words import normalize_numbers
from app.services.parse_prompt import SYSTEM_PROMPT, sentence_from_user_prompt, user_prompt
from app.services.parsing import parse_with_llm
from tests.test_eval_fixtures import SENTENCES


@pytest.mark.parametrize(
    ("text", "name", "amount", "type_", "item"),
    [
        ("rahim bhai 2 kg chal 120 taka baki", "rahim", 120, "credit", "2 kg chal"),
        ("karim 500 dilo", "karim", 500, "payment", None),
        ("salma apa pach sho taka baki, dal r tel", "salma", 500, "credit", "dal, tel"),
        ("মিজান কাকা ৩৫০ টাকার চিনি আর আটা নিল", "মিজান", 350, "credit", "চিনি, আটা"),
        ("Mr. Hasan paid 300 taka today", "Hasan", 300, "payment", None),
        ("Rahim Uddin 500 taka dilo", "Rahim Uddin", 500, "payment", None),
        ("aj jasim 300 baki", "jasim", 300, "credit", None),
    ],
)
def test_parses_common_sentences(text, name, amount, type_, item):
    result = parse_sentence(text)
    assert ParsedTransaction.model_validate(result)  # same contract as the real model
    assert (result["customer_name"], result["amount"], result["type"], result["item"]) == (
        name,
        amount,
        type_,
        item,
    )


def test_unclear_type_or_amount_lowers_confidence():
    assert parse_sentence("rahim 2 kg chal 120 taka baki")["confidence"] >= 0.8
    assert parse_sentence("rahim 2 kg chal 120 taka")["confidence"] < 0.6  # no baki/dilo
    assert parse_sentence("rahim 300 500 baki")["confidence"] < 0.6  # which number?


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("rina 2 ta saban r 1 packet biscuit", "no amount"),
        ("200 taka dilo", "no customer name"),
    ],
)
def test_missing_name_or_amount_is_an_error(text, error):
    assert parse_sentence(text) == {"error": error}


def test_handles_most_eval_sentences():
    """A demo parser, not the real thing, but it should get the regular sentences right."""
    correct = 0
    for case in SENTENCES:
        expected, got = case["expected"], parse_sentence(case["text"])
        correct += (
            clean_name(got.get("customer_name", "")).lower()
            == clean_name(expected["customer_name"]).lower()
            and got.get("amount") == expected["amount"]
            and got.get("type") == expected["type"]
        )
    assert correct >= len(SENTENCES) - 2


def test_reads_the_sentence_back_out_of_the_prompt():
    for text in ("karim 500 dilo", "salma pach sho baki"):
        assert sentence_from_user_prompt(user_prompt(text, normalize_numbers(text))) == text


def test_works_as_an_llm_client_in_the_real_pipeline():
    parsed = parse_with_llm(RuleBasedLLMClient(), "salma apa pach sho taka baki, dal r tel")
    assert (parsed.customer_name, parsed.amount, parsed.item) == ("salma", 500, "dal, tel")
    answer = RuleBasedLLMClient().complete_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt("karim 500 dilo", "karim 500 dilo")},
        ]
    )
    assert json.loads(answer)["type"] == "payment"
