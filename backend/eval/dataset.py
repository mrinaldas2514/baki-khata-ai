"""The labelled sentences: eval/data/sentences.json, plus the shopkeepers' own in my_sentences.csv.

my_sentences.csv has the columns text, customer_name, amount, type, item (see
my_sentences.template.csv). Rows with the same text one after another are one sentence with
several entries; a row with no customer_name and no amount is a sentence that should be refused
(not a transaction).
"""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATA_FILE = EVAL_DIR / "data" / "sentences.json"
MY_SENTENCES_FILE = EVAL_DIR / "my_sentences.csv"
MY_SENTENCES_CATEGORY = "my_sentences"

_TYPES = {"credit": "credit", "baki": "credit", "payment": "payment", "joma": "payment"}
_BANGLA_RE = re.compile(r"[ঀ-৿]")
_LATIN_RE = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class ExpectedEntry:
    customer_name: str
    amount: int
    type: str
    item: str | None = None
    # Other answers that also count as right (e.g. a typo'd name the model may correct).
    name_also: tuple[str, ...] = ()
    item_also: tuple[str | None, ...] = ()

    def as_dict(self) -> dict:
        return {
            "customer_name": self.customer_name,
            "amount": self.amount,
            "type": self.type,
            "item": self.item,
        }


@dataclass(frozen=True)
class Sentence:
    id: str
    text: str
    category: str
    language: str
    # Empty: not a transaction (or no amount); the parser should refuse it.
    expected: tuple[ExpectedEntry, ...]
    source: str = "eval set"
    note: str | None = None


class DatasetError(ValueError):
    pass


def _entry(data: dict) -> ExpectedEntry:
    return ExpectedEntry(
        customer_name=data["customer_name"],
        amount=data["amount"],
        type=data["type"],
        item=data.get("item"),
        name_also=tuple(data.get("name_also", ())),
        item_also=tuple(data.get("item_also", ())),
    )


def load_eval_set(path: Path = DATA_FILE) -> list[Sentence]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Sentence(
            id=row["id"],
            text=row["text"],
            category=row["category"],
            language=row["language"],
            expected=tuple(_entry(e) for e in row["expected"]),
            note=row.get("note"),
        )
        for row in data["sentences"]
    ]


def guess_language(text: str) -> str:
    bangla, latin = bool(_BANGLA_RE.search(text)), bool(_LATIN_RE.search(text))
    if bangla and latin:
        return "mixed"
    return "bangla" if bangla else "banglish"


def load_my_sentences(path: Path = MY_SENTENCES_FILE) -> list[Sentence]:
    """The shopkeepers' own sentences. A missing file is simply no sentences."""
    if not path.exists():
        return []
    sentences: list[Sentence] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"text", "customer_name", "amount", "type", "item"} - set(reader.fieldnames or ())
        if missing:
            raise DatasetError(f"{path.name}: missing column(s) {', '.join(sorted(missing))}")
        groups: list[tuple[str, list[tuple[int, dict]]]] = []
        for line, row in enumerate(reader, start=2):
            text = (row["text"] or "").strip()
            if not text:
                continue
            if groups and groups[-1][0] == text:
                groups[-1][1].append((line, row))
            else:
                groups.append((text, [(line, row)]))
    for n, (text, rows) in enumerate(groups, start=1):
        entries = [e for line, row in rows if (e := _csv_entry(path, line, row)) is not None]
        sentences.append(
            Sentence(
                id=f"my-{n:03d}",
                text=text,
                category=MY_SENTENCES_CATEGORY,
                language=guess_language(text),
                expected=tuple(entries),
                source=path.name,
            )
        )
    return sentences


def _csv_entry(path: Path, line: int, row: dict) -> ExpectedEntry | None:
    name = (row["customer_name"] or "").strip()
    amount = (row["amount"] or "").strip().replace(",", "")
    if not name and not amount:
        return None  # not a transaction
    where = f"{path.name} line {line}"
    if not name or not amount:
        raise DatasetError(f"{where}: give both customer_name and amount, or neither")
    if not amount.isdigit() or int(amount) <= 0:
        raise DatasetError(f"{where}: amount must be a whole number of taka, got {amount!r}")
    type_ = _TYPES.get((row["type"] or "").strip().lower())
    if type_ is None:
        raise DatasetError(f"{where}: type must be credit (baki) or payment (joma)")
    return ExpectedEntry(name, int(amount), type_, (row["item"] or "").strip() or None)


def load_all(
    data: Path = DATA_FILE, my_sentences: Path | None = MY_SENTENCES_FILE
) -> list[Sentence]:
    sentences = load_eval_set(data)
    if my_sentences is not None:
        sentences += load_my_sentences(my_sentences)
    return sentences
