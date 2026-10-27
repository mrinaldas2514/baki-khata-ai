"""Match the name the shopkeeper said ("Rahim bhai", "rohim", "রহিম") to an existing customer.

Every name, the spoken one and each stored one, goes through the same steps:

1. Split into words and drop honorifics/relation words (bhai, apa, da, di, kaka, mama...).
2. Write Bangla script in English letters ("রহিম" -> "rahim"), so either script matches.
3. Build a rough phonetic key that ignores common Banglish spelling differences
   ("Rohim"/"Rahim", "Shalma"/"Salma", "Kareem"/"Karim", "Zakir"/"Jakir").

Then each customer gets a 0-100 similarity score and the result is one of:

* ``exact``     - exactly one customer has the same name (ignoring case, honorifics and script)
* ``fuzzy``     - no exact match, but one customer is clearly the closest
* ``ambiguous`` - several customers fit about equally well; the shopkeeper must choose
* ``new``       - nobody is close; this is probably a new customer
"""

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar

from rapidfuzz import fuzz

# A customer this close (0-100) is matched automatically, if no one else is nearly as close.
MATCH_SCORE = 92
# How far ahead of the runner-up the best customer must be to count as a clear match.
MATCH_MARGIN = 8
# Customers at least this close are offered as candidates.
CANDIDATE_SCORE = 75
MAX_CANDIDATES = 5

_HONORIFICS = {
    unicodedata.normalize("NFC", w)
    for w in (
        # Banglish / English
        "bhai", "bhaia", "bhaiya", "bhaiyya", "vai", "vaia", "vaiya", "bhaijan", "vaijan",
        "apa", "appa", "aapa", "apu", "afa",
        "da", "dada", "di", "didi",
        "kaka", "kaku", "mama", "mami", "chacha", "chachi", "khala", "khalu",
        "fupu", "phupu", "bhabi", "vabi", "boudi", "bou",
        "sir", "saheb", "shaheb", "sahib", "ji", "uncle", "aunty", "auntie", "bro", "mr", "mrs",
        # Bangla script
        "ভাই", "ভাইয়া", "ভাইজান", "আপা", "আপু", "দা", "দাদা", "দি", "দিদি",
        "কাকা", "কাকু", "মামা", "মামি", "চাচা", "চাচি", "খালা", "খালু",
        "ভাবি", "বৌদি", "সাহেব", "স্যার", "জি",
    )
}  # fmt: skip
# Honorifics that are sometimes written joined to the name: "rahimbhai", "রহিমভাই".
_JOINED_HONORIFICS = ("bhaiya", "bhai", "vai", "ভাই")

_WORD_RE = re.compile(r"[A-Za-zঀ-৿]+")

T = TypeVar("T")

# --- Bangla script -> English letters (rough, only used for matching) -------------------

_INDEPENDENT_VOWELS = {
    "অ": "a", "আ": "a", "ই": "i", "ঈ": "i", "উ": "u", "ঊ": "u", "ঋ": "ri",
    "এ": "e", "ঐ": "oi", "ও": "o", "ঔ": "ou",
}  # fmt: skip
_VOWEL_SIGNS = {
    "া": "a", "ি": "i", "ী": "i", "ু": "u", "ূ": "u", "ৃ": "ri",
    "ে": "e", "ৈ": "oi", "ো": "o", "ৌ": "ou",
}  # fmt: skip
_CONSONANTS = {
    "ক": "k", "খ": "kh", "গ": "g", "ঘ": "gh", "ঙ": "ng",
    "চ": "ch", "ছ": "chh", "জ": "j", "ঝ": "jh", "ঞ": "n",
    "ট": "t", "ঠ": "th", "ড": "d", "ঢ": "dh", "ণ": "n",
    "ত": "t", "থ": "th", "দ": "d", "ধ": "dh", "ন": "n",
    "প": "p", "ফ": "f", "ব": "b", "ভ": "bh", "ম": "m",
    "য": "j", "র": "r", "ল": "l", "শ": "sh", "ষ": "sh", "স": "s", "হ": "h",
}  # fmt: skip
# Consonant + nukta (how NFC spells ড় ঢ় য়).
_NUKTA_CONSONANTS = {"ড": "r", "ঢ": "rh", "য": "y"}
_OTHER = {"ৎ": "t", "ং": "ng", "ঃ": "h", "ঁ": ""}
_NUKTA, _HASANT = "়", "্"


def _transliterate_word(word: str) -> str:
    """Romanize one Bangla word: 'রহিম' -> 'rahim', 'সালমা' -> 'salma'."""
    out: list[str] = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        if ch in _CONSONANTS:
            sound = _CONSONANTS[ch]
            if i + 1 < n and word[i + 1] == _NUKTA:
                sound = _NUKTA_CONSONANTS.get(ch, sound)
                i += 1
            nxt = word[i + 1] if i + 1 < n else ""
            if nxt in _VOWEL_SIGNS:
                out.append(sound + _VOWEL_SIGNS[nxt])
                i += 2
                continue
            if nxt == _HASANT:
                out.append(sound)
                i += 2
                continue
            # Inherent vowel: dropped at the end of a word, and before a consonant that
            # carries its own vowel sign (except on the first letter): সালমা -> salma.
            after = word[i + 2] if i + 2 < n else ""
            drops = not nxt or (out and nxt in _CONSONANTS and after in _VOWEL_SIGNS)
            out.append(sound if drops else sound + "a")
        elif ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
        elif ch in _VOWEL_SIGNS:
            out.append(_VOWEL_SIGNS[ch])
        elif ch in _OTHER:
            out.append(_OTHER[ch])
        elif ch.isascii():
            out.append(ch)
        i += 1
    return "".join(out)


# --- Phonetic key ------------------------------------------------------------------------

_PHONETIC_RULES = [
    ("chh", "c"), ("ch", "c"), ("ph", "f"), ("bh", "b"), ("kh", "k"), ("gh", "g"),
    ("jh", "j"), ("th", "t"), ("dh", "d"), ("sh", "s"), ("rh", "r"),
    ("ee", "i"), ("oo", "u"), ("q", "k"), ("z", "j"), ("v", "b"), ("w", "o"), ("y", "i"),
    # Bangla's inherent vowel is written as either "a" or "o": Rahim / Rohim.
    ("o", "a"),
]  # fmt: skip
_REPEATS_RE = re.compile(r"(.)\1+")


def _phonetic(word: str) -> str:
    for old, new in _PHONETIC_RULES:
        word = word.replace(old, new)
    return _REPEATS_RE.sub(r"\1", word)


# --- Public API --------------------------------------------------------------------------


def _strip_joined_honorific(word: str) -> str:
    for suffix in _JOINED_HONORIFICS:
        stem = word.removesuffix(suffix)
        if stem != word and len(stem) >= 3:
            return stem
    return word


def is_honorific(word: str) -> bool:
    return unicodedata.normalize("NFC", word.lower()) in _HONORIFICS


def name_words(name: str) -> list[str]:
    """The words of a name without honorifics, as written (lowercased)."""
    words = [w.lower() for w in _WORD_RE.findall(unicodedata.normalize("NFC", name))]
    kept = [_strip_joined_honorific(w) for w in words if w not in _HONORIFICS]
    # A customer could really be saved as just "Mama"; then keep what was written.
    return kept or words


def clean_name(name: str) -> str:
    """Display form for a new customer: honorifics removed, English letters title-cased."""
    words = name_words(name)
    return " ".join(w.capitalize() if w.isascii() else w for w in words) or name.strip()


@dataclass(frozen=True)
class _NameKey:
    plain: str  # romanized words joined by spaces
    phonetic: str  # phonetic key of each word joined by spaces

    @classmethod
    def of(cls, name: str) -> "_NameKey":
        romanized = [r for w in name_words(name) if (r := _transliterate_word(w))]
        return cls(" ".join(romanized), " ".join(_phonetic(w) for w in romanized))


def _text_similarity(plain_a: str, phonetic_a: str, plain_b: str, phonetic_b: str) -> float:
    score = max(fuzz.ratio(plain_a, plain_b), fuzz.ratio(phonetic_a, phonetic_b))
    # Spelling variants rarely change the first sound; Karim and Rahim are different people.
    if phonetic_a[0] != phonetic_b[0]:
        score -= 15
    return score


def _similarity(query: _NameKey, candidate: _NameKey) -> float:
    if not query.plain or not candidate.plain:
        return 0.0
    score = _text_similarity(query.plain, query.phonetic, candidate.plain, candidate.phonetic)

    # "Salma" vs "Salma Begum": one name is part of the other. Each word of the shorter name
    # is compared with its closest word in the longer one. Good, but less than exact.
    short, long = sorted((query, candidate), key=lambda k: len(k.plain.split()))
    if len(short.plain.split()) < len(long.plain.split()):
        long_words = list(zip(long.plain.split(), long.phonetic.split(), strict=True))
        per_word = [
            max(_text_similarity(p, ph, lp, lph) for lp, lph in long_words)
            for p, ph in zip(short.plain.split(), short.phonetic.split(), strict=True)
        ]
        score = max(score, 0.95 * sum(per_word) / len(per_word))
    return max(score, 0.0)


class MatchStatus(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    AMBIGUOUS = "ambiguous"
    NEW = "new"


@dataclass
class NameMatch(Generic[T]):
    status: MatchStatus
    # The chosen customer for exact/fuzzy, otherwise None.
    match: T | None
    # Closest customers first, as (customer, score 0-100).
    candidates: list[tuple[T, int]] = field(default_factory=list)


def match_name(
    name: str, customers: Sequence[T], get_name: Callable[[T], str] = lambda c: c.name
) -> NameMatch[T]:
    """Find which of `customers` the spoken `name` refers to."""
    query = _NameKey.of(name)
    scored = []
    exact = []
    for customer in customers:
        key = _NameKey.of(get_name(customer))
        if key.plain == query.plain:
            exact.append(customer)
            scored.append((customer, 100))
        else:
            scored.append((customer, min(round(_similarity(query, key)), 99)))

    scored.sort(key=lambda pair: -pair[1])
    candidates = [pair for pair in scored if pair[1] >= CANDIDATE_SCORE][:MAX_CANDIDATES]

    if len(exact) == 1:
        return NameMatch(MatchStatus.EXACT, exact[0], candidates)
    if len(exact) > 1:
        # Same name, different area/note: only the shopkeeper knows which one.
        return NameMatch(MatchStatus.AMBIGUOUS, None, candidates)
    if candidates:
        best_score = candidates[0][1]
        runner_up = candidates[1][1] if len(candidates) > 1 else 0
        if best_score >= MATCH_SCORE and best_score - runner_up >= MATCH_MARGIN:
            return NameMatch(MatchStatus.FUZZY, candidates[0][0], candidates)
        return NameMatch(MatchStatus.AMBIGUOUS, None, candidates)
    return NameMatch(MatchStatus.NEW, None, [])
