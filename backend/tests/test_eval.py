"""The accuracy evaluation (backend/eval): its data, its scoring and its reports.

These never call the real AI: the LLM is the rule-based parser or a scripted fake.
"""

import json
import re
from collections import Counter
from datetime import date

import groq
import httpx
import pytest

from app.config import Settings
from app.llm import LLMProviderError
from app.llm.rule_based import RuleBasedLLMClient
from app.schemas import ParsedTransaction
from eval import run_eval
from eval.dataset import (
    EVAL_DIR,
    DatasetError,
    ExpectedEntry,
    Sentence,
    load_eval_set,
    load_my_sentences,
)
from eval.scoring import Got, percentile, same_item, score_entry, score_sentence
from tests.conftest import FakeLLM

SENTENCES = load_eval_set()
CATEGORIES = {
    "banglish_credit", "banglish_payment", "bangla_script", "english", "code_mixed",
    "number_words", "bangla_digits", "honorifics", "items", "typos", "past_payment",
    "multi_entry", "no_amount", "non_transaction",
}  # fmt: skip


# --- The labelled sentences ---------------------------------------------------------------


def test_at_least_150_unique_sentences_in_every_category():
    assert len(SENTENCES) >= 150
    assert len({s.id for s in SENTENCES}) == len(SENTENCES)
    assert len({s.text for s in SENTENCES}) == len(SENTENCES)
    per_category = Counter(s.category for s in SENTENCES)
    assert set(per_category) == CATEGORIES
    assert min(per_category.values()) >= 10
    assert {s.language for s in SENTENCES} == {"banglish", "bangla", "english", "mixed"}


def test_covers_the_hard_parts():
    texts = " ".join(s.text for s in SENTENCES)
    for phrase in (
        "pach sho", "dedh hajar", "arai sho", "sowa sho", "shodh korlo", "joma dilo",
        "ferot dilo", "২", "bhai", "apa", "da ",
    ):  # fmt: skip
        assert phrase in texts, phrase
    assert sum(len(s.expected) > 1 for s in SENTENCES) >= 10
    assert {e.type for s in SENTENCES for e in s.expected} == {"credit", "payment"}
    assert all(not s.expected for s in SENTENCES if s.category in ("no_amount", "non_transaction"))


@pytest.mark.parametrize("sentence", SENTENCES, ids=lambda s: s.id)
def test_expected_entries_follow_the_parse_contract(sentence: Sentence):
    for entry in sentence.expected:
        ParsedTransaction.model_validate(entry.as_dict() | {"confidence": 1})


def test_the_old_fixture_sentences_are_all_in_the_eval_set():
    from tests.test_eval_fixtures import SENTENCES as OLD

    texts = {s.text for s in SENTENCES}
    assert {s["text"] for s in OLD} <= texts


# --- Scoring ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("got", "expected"),
    [
        ("dal r tel", "dal, tel"),
        ("tel and dal", "dal, tel"),
        ("২ কেজি আলু", "2 কেজি আলু"),
        ("2kg chal", "2 kg chal"),
        (None, None),
    ],
)
def test_items_compare_as_the_same_words(got, expected):
    assert same_item(got, expected)


@pytest.mark.parametrize(("got", "expected"), [("dal", "dal, tel"), (None, "chal"), ("chal", None)])
def test_different_items(got, expected):
    assert not same_item(got, expected)


def test_names_compare_like_customer_matching():
    expected = ExpectedEntry("rahim", 120, "credit", "2 kg chal")
    for name in ("Rahim", "rahim bhai", "Rohim", "রহিম"):
        assert score_entry(Got(name, 120, "credit", "2 kg chal"), expected)["name"], name
    assert not score_entry(Got("Rahima", 120, "credit", "2 kg chal"), expected)["name"]
    typo = ExpectedEntry("rhim", 300, "credit", name_also=("rahim",))
    assert score_entry(Got("Rahim", 300, "credit", None), typo)["name"]


def test_sentence_scores():
    two = Sentence(
        "x", "rahim 200 baki, karim 500 dilo", "multi_entry", "banglish",
        (ExpectedEntry("rahim", 200, "credit"), ExpectedEntry("karim", 500, "payment")),
    )  # fmt: skip
    both = [Got("Rahim", 200, "credit", None), Got("Karim", 500, "payment", None)]
    assert score_sentence(two, both).all_correct
    only_first = score_sentence(two, both[:1])
    assert not only_first.all_correct
    assert only_first.fields[1] == dict.fromkeys(("name", "amount", "type", "item"), False)

    refuse = Sentence("y", "aj dokan bondho", "non_transaction", "banglish", ())
    assert score_sentence(refuse, []).all_correct
    made_up = score_sentence(refuse, [Got("aj", 1, "credit", None)])
    assert not made_up.all_correct and made_up.extra_entries == 1


def test_percentile():
    assert percentile(list(range(1, 21)), 95) == 19
    assert percentile([5.0], 95) == 5.0
    assert percentile([], 95) == 0.0


# --- my_sentences.csv ---------------------------------------------------------------------


def test_template_has_three_example_rows():
    template = EVAL_DIR / "my_sentences.template.csv"
    assert len(template.read_text(encoding="utf-8").strip().splitlines()) == 1 + 3
    sentences = load_my_sentences(template)
    assert [len(s.expected) for s in sentences] == [1, 2]  # the last two rows: one sentence


def test_my_sentences_rows(tmp_path):
    path = tmp_path / "my_sentences.csv"
    path.write_text(
        "﻿text,customer_name,amount,type,item\n"
        "rahim bhai 120 taka baki,rahim,120,baki,\n"
        '"karim 500 dilo, salma 200 baki",karim,500,payment,\n'
        '"karim 500 dilo, salma 200 baki",salma,200,credit,\n'
        "দোকান বন্ধ,,,,\n"
        ",,,,\n",
        encoding="utf-8",
    )
    sentences = load_my_sentences(path)
    assert [s.text for s in sentences] == [
        "rahim bhai 120 taka baki", "karim 500 dilo, salma 200 baki", "দোকান বন্ধ",
    ]  # fmt: skip
    assert sentences[0].expected == (ExpectedEntry("rahim", 120, "credit"),)
    assert [e.customer_name for e in sentences[1].expected] == ["karim", "salma"]
    assert sentences[2].expected == ()  # not a transaction
    assert {s.category for s in sentences} == {"my_sentences"}
    assert sentences[2].language == "bangla"


@pytest.mark.parametrize(
    ("row", "problem"),
    [
        ("rahim 100 baki,rahim,,credit,", "both customer_name and amount"),
        ("rahim 100 baki,rahim,100.5,credit,", "whole number"),
        ("rahim 100 baki,rahim,100,owes,", "credit (baki) or payment (joma)"),
    ],
)
def test_my_sentences_mistakes_are_explained(tmp_path, row, problem):
    path = tmp_path / "my_sentences.csv"
    path.write_text(f"text,customer_name,amount,type,item\n{row}\n", encoding="utf-8")
    with pytest.raises(DatasetError, match=re.escape(problem)):
        load_my_sentences(path)


def test_no_my_sentences_file_is_fine(tmp_path):
    assert load_my_sentences(tmp_path / "missing.csv") == []


# --- Running it ---------------------------------------------------------------------------


def one(name, amount, type_="credit", item=None, confidence=0.9):
    entry = {"customer_name": name, "amount": amount, "type": type_, "item": item}
    return {"entries": [entry | {"confidence": confidence}]}


def test_evaluate_with_a_scripted_llm(fake_llm: FakeLLM):
    sentences = [
        Sentence("a", "rahim 200 baki", "banglish_credit", "banglish", (ExpectedEntry("rahim", 200, "credit"),)),
        Sentence("b", "karim 500 dilo", "banglish_payment", "banglish", (ExpectedEntry("karim", 500, "payment"),)),
        Sentence("c", "aj dokan bondho", "non_transaction", "banglish", ()),
        Sentence("d", "salma 300 baki", "banglish_credit", "banglish", (ExpectedEntry("salma", 300, "credit"),)),
    ]  # fmt: skip
    fake_llm.reply(
        one("Rahim", 200),
        one("karim", 500, "credit"),  # wrong type
        {"error": "not a transaction"},
        LLMProviderError("down"),
    )
    results = run_eval.evaluate(fake_llm, sentences)
    assert [r.outcome for r in results] == ["parsed", "parsed", "refused", "provider_error"]
    assert [r.score.all_correct for r in results] == [True, False, True, False]

    summary = run_eval.summarize(results)
    assert summary["all_correct"] == {"correct": 2, "total": 4, "rate": 0.5}
    assert summary["fields"]["type"] == {"correct": 1, "total": 3, "rate": 1 / 3}
    assert summary["non_transactions_refused"]["rate"] == 1.0
    assert summary["categories"]["banglish_credit"]["correct"] == 1
    assert summary["outcomes"] == {"parsed": 2, "refused": 1, "provider_error": 1}


def rate_limited(retry_after: str) -> LLMProviderError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": retry_after})
    try:
        raise groq.RateLimitError("Slow down", response=response, body=None)
    except groq.RateLimitError as cause:
        error = LLMProviderError("rate limited")
        error.__cause__ = cause
        return error


def test_rate_limits_are_waited_out_and_not_counted_as_latency(fake_llm: FakeLLM):
    waits = []
    fake_llm.reply(rate_limited("7"), one("rahim", 200))
    timed = run_eval.TimedLLM(fake_llm, sleep=waits.append)
    assert json.loads(timed.complete_json([{"role": "user", "content": "x"}]))["entries"]
    assert waits == [7.0]
    assert timed.elapsed < 1  # the 7 s wait isn't in it


def test_other_provider_errors_are_not_retried(fake_llm: FakeLLM):
    fake_llm.reply(LLMProviderError("bad key"))
    with pytest.raises(LLMProviderError):
        run_eval.TimedLLM(fake_llm, sleep=lambda _s: pytest.fail("slept")).complete_json([])


def test_rules_run_writes_markdown_and_json(tmp_path, capsys):
    assert (
        run_eval.main(
            [
                "--parser",
                "rules",
                "--out",
                str(tmp_path),
                "--my-sentences",
                str(tmp_path / "none.csv"),
            ]
        )
        == 0
    )
    stem = f"{date.today().isoformat()}_rules_rule-based"
    md = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
    data = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))

    for heading in ("## Summary", "## By category", "## By language", "## Failures"):
        assert heading in md
    assert "Latency per sentence, p95" in md
    assert data["parser"] == "rules" and data["model"] == "rule-based"
    assert data["summary"]["sentences"] == len(SENTENCES)
    assert set(data["summary"]["categories"]) == CATEGORIES
    failure = next(r for r in data["results"] if not r["all_correct"])
    assert {"text", "expected", "got"} <= set(failure)
    assert "all fields correct" in capsys.readouterr().out


def test_rule_based_parser_does_not_get_worse():
    """A floor under the committed result (eval/results/): change the rules, keep this green."""
    summary = run_eval.summarize(run_eval.evaluate(RuleBasedLLMClient(), SENTENCES))
    assert summary["all_correct"]["rate"] >= 0.88
    assert summary["fields"]["amount"]["rate"] >= 0.95


def test_llm_without_a_key_stops_with_a_clear_message(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run_eval, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(groq, "Groq", lambda **_kw: pytest.fail("must not call Groq"))
    for parser in ("llm", "both"):
        assert run_eval.main(["--parser", parser, "--out", str(tmp_path)]) == 2
        assert "needs GROQ_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


class EchoLLM(RuleBasedLLMClient):
    """Pretends to be a model, answering like the rules (no network)."""

    parser = "llm"
    model = "openai/echo-1"


def test_both_writes_a_side_by_side_comparison(monkeypatch, tmp_path):
    monkeypatch.setattr(
        run_eval,
        "build_parser",
        lambda kind, _model: EchoLLM() if kind == "llm" else RuleBasedLLMClient(),
    )
    assert run_eval.main(["--parser", "both", "--out", str(tmp_path), "--limit", "20"]) == 0
    today = date.today().isoformat()
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == sorted(
        f"{today}_{stem}.{ext}"
        for stem in ("rules_rule-based", "llm_openai-echo-1", "both_rule-based_vs_openai-echo-1")
        for ext in ("md", "json")
    )
    comparison = (tmp_path / f"{today}_both_rule-based_vs_openai-echo-1.md").read_text(
        encoding="utf-8"
    )
    assert "| Metric | rules (`rule-based`) | llm (`openai/echo-1`) |" in comparison
    assert "## Right only with llm (0)" in comparison
