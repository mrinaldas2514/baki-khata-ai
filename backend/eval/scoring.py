"""Is a parser's answer right? Compared the way the app would use it.

- customer name: the same name to customer matching (case, honorifics, Bangla or English
  letters and Banglish spelling ignored: "Rahim bhai" = "rohim" = "রহিম");
- amount and type: exactly;
- item: the same words in any order ("dal, tel" = "dal r tel" = "tel and dal"), with Bangla
  digits read as digits.

Entries are compared in order: the first answer with the first expected entry, and so on.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from app.services.name_matching import same_name
from eval.dataset import ExpectedEntry, Sentence

FIELDS = ("name", "amount", "type", "item")

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_ITEM_WORD_RE = re.compile(r"\d+|[a-zঀ-৿]+")
# Words that only join or decorate items.
_ITEM_FILLER = {"r", "ar", "and", "o", "&", "of", "a", "an", "the", "আর", "ও"}


@dataclass(frozen=True)
class Got:
    """One entry as the parser gave it."""

    customer_name: str
    amount: int
    type: str
    item: str | None

    def as_dict(self) -> dict:
        return {
            "customer_name": self.customer_name,
            "amount": self.amount,
            "type": self.type,
            "item": self.item,
        }


def item_words(item: str | None) -> Counter:
    if not item:
        return Counter()
    text = unicodedata.normalize("NFC", item).lower().translate(_BANGLA_DIGITS)
    return Counter(w for w in _ITEM_WORD_RE.findall(text) if w not in _ITEM_FILLER)


def same_item(got: str | None, expected: str | None) -> bool:
    return item_words(got) == item_words(expected)


def score_entry(got: Got, expected: ExpectedEntry) -> dict[str, bool]:
    names = (expected.customer_name, *expected.name_also)
    items = (expected.item, *expected.item_also)
    return {
        "name": any(same_name(got.customer_name, name) for name in names),
        "amount": got.amount == expected.amount,
        "type": got.type == expected.type,
        "item": any(same_item(got.item, item) for item in items),
    }


@dataclass
class SentenceScore:
    # One {field: correct} per expected entry; all False where the parser gave no entry.
    fields: list[dict[str, bool]]
    # The parser gave more entries than expected (or any, for a non-transaction).
    extra_entries: int
    all_correct: bool


def score_sentence(sentence: Sentence, got: list[Got]) -> SentenceScore:
    fields = []
    for i, expected in enumerate(sentence.expected):
        if i < len(got):
            fields.append(score_entry(got[i], expected))
        else:
            fields.append(dict.fromkeys(FIELDS, False))
    extra = max(0, len(got) - len(sentence.expected))
    all_correct = (
        extra == 0
        and len(got) == len(sentence.expected)
        and all(all(entry.values()) for entry in fields)
    )
    return SentenceScore(fields=fields, extra_entries=extra, all_correct=all_correct)


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (p95 of 20 values is the 19th smallest)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]
