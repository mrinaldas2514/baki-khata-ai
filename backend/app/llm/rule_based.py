"""A rule-based stand-in for the LLM, so the app can be run and demoed without an API key.

Enable it with LLM_PROVIDER=fake (or leave GROQ_API_KEY empty with LLM_PROVIDER=auto). It
answers with the same JSON the real model is asked for, so the rest of the pipeline
(validation, sanity check, customer name matching) runs unchanged.

It handles the common shapes well and nothing more:

    "rahim bhai 2 kg chal 120 taka baki"        -> rahim, 120, credit, "2 kg chal"
    "salma apa pach sho taka baki, dal r tel"   -> salma, 500, credit, "dal, tel"
    "Karim 500 dilo"                            -> Karim, 500, payment
    "মিজান কাকা ৩৫০ টাকার চিনি আর আটা নিল"         -> মিজান, 350, credit, "চিনি, আটা"

The name is the first word (plus a capitalized surname), the amount is the number next to
"taka" (or else the number that isn't a quantity like "2 kg"), and the type comes from
keywords. Use the real model for anything less regular.

Several entries in one sentence are split at commas, semicolons and new lines, but only when
every part is a whole entry with its own name and amount:

    "rahim 200 baki, karim 500 dilo"   -> two entries
    "salma 500 taka baki, dal r tel"    -> one entry ("dal r tel" has no name or amount)
"""

import json
import re
import unicodedata
from dataclasses import dataclass

from app.llm.base import ChatMessage
from app.services.name_matching import is_honorific
from app.services.number_words import normalize_numbers
from app.services.parse_prompt import sentence_from_user_prompt

MAX_ITEM_LENGTH = 200
# The "model" name reported for parses done by these rules.
RULES_MODEL = "rule-based"


def _nfc_set(*words: str) -> frozenset[str]:
    return frozenset(unicodedata.normalize("NFC", w) for w in words)


_CREDIT = _nfc_set(
    "baki", "baaki", "bakee", "nilo", "nilen", "nise", "nisen", "niyeche", "niyechhe",
    "dhar", "udhar", "took", "owes", "due", "credit", "rakhlo", "rakhlen", "rakhse",
    "বাকি", "বাকী", "নিল", "নিলো", "নিলেন", "নিয়েছে", "ধার", "রাখল", "রাখলো",
)  # fmt: skip
_PAYMENT = _nfc_set(
    "dilo", "dilen", "dise", "disen", "diyeche", "diyechhe", "jama", "joma", "shodh",
    "sodh", "porishodh", "paid", "gave", "returned", "payment",
    "দিল", "দিলো", "দিলেন", "দিয়েছে", "জমা", "শোধ", "পরিশোধ",
)  # fmt: skip
_CURRENCY = _nfc_set(
    "taka", "takar", "takay", "tk", "tka", "rs", "rupee", "rupees", "inr", "bdt", "৳",
    "টাকা", "টাকার", "টাকায়",
)  # fmt: skip
_UNITS = _nfc_set(
    "kg", "kilo", "g", "gm", "gram", "ta", "ti", "pc", "pcs", "piece", "pieces", "packet",
    "pkt", "liter", "litre", "ltr", "l", "dozen", "hali", "bosta", "cup", "bottle",
    "কেজি", "গ্রাম", "টা", "টি", "প্যাকেট", "লিটার", "হালি", "ডজন", "বস্তা",
)  # fmt: skip
# Joins items: "dal r tel", "dal, tel".
_SEPARATORS = _nfc_set("r", "ar", "and", "o", "আর", "ও", ",", ";", "/", ".")
# Small words that are neither name nor item.
_FILLER = _nfc_set(
    "er", "ke", "theke", "aj", "ajke", "today", "kal", "gotokal", "yesterday", "the", "of",
    "for", "worth", "amount", "korlo", "korlen", "korse", "kore",
    "আজ", "আজকে", "গতকাল", "কাল", "কে", "এর", "করল", "করলো", "করলেন",
)  # fmt: skip

# "৳" sits inside the Bangla Unicode block, so it is matched before Bangla letters.
_TOKEN_RE = re.compile(r"৳|\d+|[A-Za-zঀ-৲৴-৿]+|[,;/.]")
_ENTRY_SEPARATOR_RE = re.compile(r"[,;\n]")
MAX_ENTRIES = 10


@dataclass
class _Token:
    text: str

    @property
    def key(self) -> str:
        return self.text.lower()

    @property
    def is_number(self) -> bool:
        return self.text.isdigit()

    @property
    def is_keyword(self) -> bool:
        return self.key in _CREDIT or self.key in _PAYMENT

    @property
    def is_word(self) -> bool:
        return not self.is_number and self.key not in _SEPARATORS and self.text != "৳"


class RuleBasedLLMClient:
    """LLMClient that parses with simple rules instead of calling a model."""

    parser = "rules"
    model = RULES_MODEL

    def complete_json(self, messages: list[ChatMessage]) -> str:
        first_user = next(m["content"] for m in messages if m["role"] == "user")
        return json.dumps(parse_text(sentence_from_user_prompt(first_user)), ensure_ascii=False)


def parse_text(sentence: str) -> dict:
    """The whole sentence: one entry, or {"entries": [...]} when it lists several customers."""
    # Numbers first, so "2,500" isn't split at its comma.
    parts = [p for p in _ENTRY_SEPARATOR_RE.split(normalize_numbers(sentence)) if p.strip()]
    if 1 < len(parts) <= MAX_ENTRIES:
        entries = [parse_sentence(part) for part in parts]
        if all("error" not in entry for entry in entries):
            return {"entries": entries}
    return parse_sentence(sentence)


def parse_sentence(sentence: str) -> dict:
    """One sentence -> the JSON object the LLM contract asks for (or {"error": ...})."""
    tokens = [_Token(t) for t in _TOKEN_RE.findall(normalize_numbers(sentence))]

    name_idx = _name_tokens(tokens)
    if not name_idx:
        return {"error": "no customer name"}
    amount = _amount_token(tokens)
    if amount is None:
        return {"error": "no amount"}
    amount_idx, amount_sure = amount

    keys = {t.key for t in tokens}
    if keys & _PAYMENT:
        type_, type_sure = "payment", True
    elif keys & _CREDIT:
        type_, type_sure = "credit", True
    else:
        # Goods with no payment word count as credit, same rule as the prompt.
        type_, type_sure = "credit", False

    item = _item(tokens, set(name_idx) | {amount_idx}) if type_ == "credit" else None
    confidence = 0.8 if type_sure and amount_sure else 0.55
    return {
        "customer_name": " ".join(tokens[i].text for i in name_idx),
        "amount": int(tokens[amount_idx].text),
        "type": type_,
        "item": item,
        "confidence": confidence,
    }


def _name_tokens(tokens: list[_Token]) -> list[int]:
    """The first real word, plus a second one when both are capitalized ("Rahim Uddin")."""
    i = 0
    while i < len(tokens) and (
        tokens[i].key in _FILLER or tokens[i].key in _SEPARATORS or is_honorific(tokens[i].text)
    ):
        i += 1
    if i >= len(tokens) or not _could_be_name(tokens[i]):
        return []
    found = [i]
    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
    if (
        nxt is not None
        and _could_be_name(nxt)
        and tokens[i].text[:1].isupper()
        and nxt.text[:1].isupper()
    ):
        found.append(i + 1)
    return found


def _could_be_name(token: _Token) -> bool:
    return (
        token.is_word
        and not token.is_keyword
        and not is_honorific(token.text)
        and token.key not in _CURRENCY
        and token.key not in _UNITS
        and token.key not in _FILLER
    )


def _amount_token(tokens: list[_Token]) -> tuple[int, bool] | None:
    """Index of the money amount, and whether it is clear (next to "taka", or the only number)."""
    best: tuple[int, int, int] | None = None  # (score, value, index)
    count = 0
    for i, token in enumerate(tokens):
        if not token.is_number or int(token.text) == 0:
            continue
        before = tokens[i - 1].key if i > 0 else ""
        after = tokens[i + 1].key if i + 1 < len(tokens) else ""
        if after in _CURRENCY or before in _CURRENCY:
            score = 2
        elif after in _UNITS:
            continue  # a quantity, like "2 kg"
        else:
            score = 1
        count += 1
        candidate = (score, int(token.text), i)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None:
        return None
    return best[2], best[0] == 2 or count == 1


def _item(tokens: list[_Token], used: set[int]) -> str | None:
    """What's left once name, amount, keywords and filler are removed, grouped into items."""
    groups: list[list[str]] = [[]]
    for i, token in enumerate(tokens):
        skip = (
            i in used
            or token.is_keyword
            or token.key in _CURRENCY
            or token.key in _FILLER
            or token.key in _SEPARATORS
            or token.text == "৳"
            or is_honorific(token.text)
        )
        if skip:
            if groups[-1]:
                groups.append([])
        else:
            groups[-1].append(token.text)
    items = [" ".join(group) for group in groups if group]
    return ", ".join(items)[:MAX_ITEM_LENGTH] or None
