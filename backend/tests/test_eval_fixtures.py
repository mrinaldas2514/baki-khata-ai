"""Keep tests/fixtures/eval_sentences.json well-formed and consistent with the deterministic steps.

This does not measure the LLM (that needs the real API); it checks the parts we control.
"""

import json
from pathlib import Path

import pytest

from app.schemas import ParsedTransaction
from app.services.name_matching import name_words
from app.services.number_words import normalize_numbers, numbers_in

FIXTURE = Path(__file__).parent / "fixtures" / "eval_sentences.json"
SENTENCES = json.loads(FIXTURE.read_text(encoding="utf-8"))["sentences"]


def test_fixture_has_twenty_varied_sentences():
    assert len(SENTENCES) >= 20
    assert len({s["id"] for s in SENTENCES}) == len(SENTENCES)
    assert len({s["text"] for s in SENTENCES}) == len(SENTENCES)
    assert {s["language"] for s in SENTENCES} == {"banglish", "bangla", "english", "mixed"}
    assert {s["expected"]["type"] for s in SENTENCES} == {"credit", "payment"}


@pytest.mark.parametrize("case", SENTENCES, ids=lambda s: f"{s['id']}: {s['text']}")
def test_expected_output_is_valid(case):
    ParsedTransaction.model_validate(case["expected"] | {"confidence": 1})


@pytest.mark.parametrize("case", SENTENCES, ids=lambda s: f"{s['id']}: {s['text']}")
def test_expected_amount_is_found_after_number_normalization(case):
    # Otherwise a correct LLM answer would be flagged "amount not found in the sentence".
    assert case["expected"]["amount"] in numbers_in(normalize_numbers(case["text"]))


@pytest.mark.parametrize("case", SENTENCES, ids=lambda s: f"{s['id']}: {s['text']}")
def test_expected_name_is_in_the_sentence_without_honorifics(case):
    expected = name_words(case["expected"]["customer_name"])
    assert set(expected) <= set(name_words(case["text"]))
