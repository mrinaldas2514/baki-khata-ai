"""The LLM layer: output validation, retry, and the Groq client wrapper. No real API calls."""

import groq
import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.llm import LLMNotConfiguredError, LLMProviderError, build_llm_client
from app.llm.groq_client import GroqLLMClient
from app.llm.rule_based import RuleBasedLLMClient
from app.schemas import ParsedTransaction
from app.services.parsing import LLMOutputError, NotATransactionError, parse_with_llm
from tests.conftest import FakeLLM

GOOD = {
    "customer_name": "rahim",
    "amount": 120,
    "type": "credit",
    "item": "2 kg chal",
    "confidence": 0.95,
}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"amount": 0}, "amount"),
        ({"amount": -50}, "amount"),
        ({"amount": 12.5}, "amount"),
        ({"amount": "120"}, "amount"),
        ({"amount": None}, "amount"),
        ({"type": "loan"}, "type"),
        ({"confidence": 1.5}, "confidence"),
        ({"confidence": -0.1}, "confidence"),
        ({"customer_name": "  "}, "customer_name"),
        ({"item": "x" * 201}, "item"),
    ],
)
def test_parsed_transaction_rejects_bad_fields(changes, field):
    with pytest.raises(ValidationError) as exc_info:
        ParsedTransaction.model_validate(GOOD | changes)
    assert {err["loc"][0] for err in exc_info.value.errors()} == {field}


def test_parsed_transaction_requires_every_field_but_item():
    with pytest.raises(ValidationError) as exc_info:
        ParsedTransaction.model_validate({})
    missing = {err["loc"][0] for err in exc_info.value.errors()}
    assert missing == {"customer_name", "amount", "type", "confidence"}


def test_parsed_transaction_accepts_whole_float_and_blank_item():
    parsed = ParsedTransaction.model_validate(GOOD | {"amount": 120.0, "item": " "})
    assert parsed.amount == 120
    assert parsed.item is None


def test_valid_answer_is_used_directly(fake_llm: FakeLLM):
    fake_llm.reply(GOOD)
    parsed = parse_with_llm(fake_llm, "rahim bhai 2 kg chal 120 taka baki")
    assert parsed == ParsedTransaction.model_validate(GOOD)
    assert len(fake_llm.calls) == 1
    system, user = fake_llm.calls[0]
    assert system["role"] == "system" and "JSON" in system["content"]
    assert user == {"role": "user", "content": "Sentence: rahim bhai 2 kg chal 120 taka baki"}


def test_number_words_are_sent_as_digits_too(fake_llm: FakeLLM):
    fake_llm.reply(GOOD | {"customer_name": "salma", "amount": 500})
    parse_with_llm(fake_llm, "salma apa pach sho taka baki")
    user = fake_llm.calls[0][1]["content"]
    assert user == (
        "Sentence: salma apa pach sho taka baki\n"
        "Same sentence with numbers written as digits: salma apa 500 taka baki"
    )


def test_code_fence_around_json_is_tolerated(fake_llm: FakeLLM):
    fake_llm.reply('```json\n{"customer_name": "karim", "amount": 500, "type": "payment", '
                   '"item": null, "confidence": 0.9}\n```')  # fmt: skip
    assert parse_with_llm(fake_llm, "karim 500 dilo").amount == 500


@pytest.mark.parametrize(
    ("bad_answer", "problem"),
    [
        ("Sure! Rahim owes 120 taka.", "not valid JSON"),
        ('{"customer_name": "rahim", "amount": 120', "not valid JSON"),
        ("[1, 2, 3]", "expected a JSON object"),
        (GOOD | {"amount": "one twenty"}, "amount: Input should be a valid integer"),
        ({k: v for k, v in GOOD.items() if k != "type"}, "type: Field required"),
    ],
)
def test_invalid_answer_is_retried_once_with_the_problem(fake_llm: FakeLLM, bad_answer, problem):
    fake_llm.reply(bad_answer, GOOD)
    parsed = parse_with_llm(fake_llm, "rahim bhai 2 kg chal 120 taka baki")
    assert parsed.amount == 120
    assert len(fake_llm.calls) == 2
    retry = fake_llm.calls[1]
    # The retry repeats the conversation, then shows the bad answer and what was wrong.
    assert retry[:2] == fake_llm.calls[0]
    assert retry[2]["role"] == "assistant"
    assert retry[3]["role"] == "user" and problem in retry[3]["content"]


def test_two_invalid_answers_give_a_clear_error(fake_llm: FakeLLM):
    fake_llm.reply("not json", GOOD | {"amount": -1})
    with pytest.raises(LLMOutputError) as exc_info:
        parse_with_llm(fake_llm, "rahim 120 baki")
    message = str(exc_info.value)
    assert "invalid answer twice" in message
    assert "amount: Value error, Amount must be greater than 0" in message
    assert len(fake_llm.calls) == 2


def test_model_says_it_is_not_a_transaction(fake_llm: FakeLLM):
    fake_llm.reply({"error": "no amount"})
    with pytest.raises(NotATransactionError, match="no amount"):
        parse_with_llm(fake_llm, "rina 2 ta saban")
    assert len(fake_llm.calls) == 1  # a clear "no" is not retried


def test_provider_errors_are_not_retried_here(fake_llm: FakeLLM):
    fake_llm.reply(LLMProviderError("rate limited"))
    with pytest.raises(LLMProviderError):
        parse_with_llm(fake_llm, "karim 500 dilo")


# --- Provider wiring ----------------------------------------------------------------------


def test_groq_without_api_key_means_not_configured():
    with pytest.raises(LLMNotConfiguredError, match="GROQ_API_KEY"):
        build_llm_client(Settings(_env_file=None, llm_provider="groq", groq_api_key=None))
    with pytest.raises(LLMNotConfiguredError):
        build_llm_client(Settings(_env_file=None, llm_provider="groq", groq_api_key="  "))


def test_groq_client_is_built_from_settings():
    client = build_llm_client(
        Settings(_env_file=None, groq_api_key="test-key", groq_model="some-model")
    )
    assert isinstance(client, GroqLLMClient)
    assert client._model == "some-model"


class _FakeCompletions:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        message = type("Message", (), {"content": self.result})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


def _groq_with(monkeypatch, result) -> tuple[GroqLLMClient, _FakeCompletions]:
    client = GroqLLMClient(api_key="test-key", model="some-model")
    completions = _FakeCompletions(result)
    monkeypatch.setattr(client._client.chat, "completions", completions)
    return client, completions


def test_groq_client_asks_for_deterministic_json(monkeypatch):
    client, completions = _groq_with(monkeypatch, '{"ok": true}')
    messages = [{"role": "user", "content": "hi"}]
    assert client.complete_json(messages) == '{"ok": true}'
    assert completions.kwargs["model"] == "some-model"
    assert completions.kwargs["messages"] == messages
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["temperature"] == 0


def test_groq_errors_become_provider_errors(monkeypatch):
    error = groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))
    client, _ = _groq_with(monkeypatch, error)
    with pytest.raises(LLMProviderError):
        client.complete_json([{"role": "user", "content": "hi"}])


@pytest.mark.parametrize(
    ("provider", "key", "expected"),
    [
        ("auto", "test-key", GroqLLMClient),
        ("auto", None, RuleBasedLLMClient),
        ("fake", "test-key", RuleBasedLLMClient),
        ("groq", "test-key", GroqLLMClient),
    ],
)
def test_llm_provider_setting_picks_the_client(provider, key, expected):
    settings = Settings(_env_file=None, llm_provider=provider, groq_api_key=key)
    assert isinstance(build_llm_client(settings), expected)


def test_blank_llm_provider_means_auto():
    assert Settings(_env_file=None, llm_provider=" ").llm_provider == "auto"
    assert Settings(_env_file=None, llm_provider="FAKE").llm_provider == "fake"
