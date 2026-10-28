"""Turn Bangla digits and spoken amounts ("pach sho", "dedh hajar", "দেড় হাজার") into digits.

This runs before the LLM sees the sentence. LLMs are unreliable with Banglish number
words, while these rules are easy to get exactly right and to test:

    "salma apa pach sho taka baki"  ->  "salma apa 500 taka baki"
    "dedh hajar dilo"               ->  "1500 dilo"
    "sowa sho taka"                 ->  "125 taka"
    "রহিম ২০০ টাকা দিল"              ->  "রহিম 200 টাকা দিল"

To avoid touching ordinary words, a number word is only converted when it is followed by
a multiplier (sho / hajar / lakh) or by a currency word (taka / tk / টাকা).
"""

import re
import unicodedata

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _nfc(text: str) -> str:
    # Bangla letters like য় and ড় have two Unicode spellings; NFC makes them compare equal.
    return unicodedata.normalize("NFC", text)


def _words(mapping: dict[int | float, tuple[str, ...]]) -> dict[str, float]:
    return {_nfc(word): float(value) for value, words in mapping.items() for word in words}


_BASE = _words(
    {
        1: ("ek", "aek", "এক"),
        2: ("dui", "du", "দুই", "দু"),
        3: ("tin", "teen", "তিন"),
        4: ("char", "chaar", "চার"),
        5: ("pach", "panch", "paach", "paanch", "পাঁচ", "পাচ"),
        6: ("choy", "chhoy", "choi", "chhoi", "ছয়"),
        7: ("sat", "saat", "সাত"),
        8: ("at", "aat", "ath", "aath", "আট"),
        9: ("noy", "nou", "noi", "নয়"),
        10: ("dosh", "dos", "দশ"),
        11: ("egaro", "এগারো"),
        12: ("baro", "বারো"),
        13: ("tero", "তেরো"),
        14: ("choddo", "চৌদ্দ"),
        15: ("ponero", "pondro", "পনেরো", "পনের"),
        16: ("sholo", "ষোলো", "ষোল"),
        17: ("sotero", "সতেরো"),
        18: ("atharo", "আঠারো"),
        19: ("unish", "উনিশ"),
        20: ("bish", "kuri", "বিশ", "কুড়ি"),
        25: ("pochish", "pochis", "পঁচিশ"),
        30: ("tirish", "tiris", "ত্রিশ"),
        40: ("chollish", "chollis", "চল্লিশ"),
        50: ("ponchash", "ponchas", "pachas", "পঞ্চাশ"),
        60: ("shat", "shaat", "ষাট"),
        70: ("sottor", "sattor", "সত্তর"),
        80: ("ashi", "আশি"),
        90: ("nobboi", "নব্বই"),
    }
) | _words(
    {
        1: ("one",),
        2: ("two",),
        3: ("three",),
        4: ("four",),
        5: ("five",),
        6: ("six",),
        7: ("seven",),
        8: ("eight",),
        9: ("nine",),
        10: ("ten",),
        20: ("twenty",),
        50: ("fifty",),
    }
)
# Used on their own before a multiplier: "dedh hajar" = 1500, "arai sho" = 250.
_SOWA = ("sowa", "shoa", "showa", "soa", "soya", "shuwa", "সোয়া", "সওয়া")
_FRACTION = _words(
    {1.25: _SOWA, 1.5: ("dedh", "der", "derh", "দেড়"), 2.5: ("arai", "adai", "আড়াই")}
)
# Modify the next number: "sare tin sho" = 350, "poune dui hajar" = 1750,
# "sowa tin sho" = 325 ("sowa" alone before a multiplier is 1.25: "sowa sho" = 125).
_MODIFIERS = {
    **{_nfc(w): 0.5 for w in ("sare", "share", "sade", "saade", "সাড়ে")},
    **{_nfc(w): 0.25 for w in _SOWA},
    **{_nfc(w): -0.25 for w in ("poune", "paune", "pone", "পৌনে")},
}
_MULTIPLIER = _words(
    {
        100: ("sho", "shoo", "sow", "shoto", "sau", "so", "hundred", "শো", "শ", "শত"),
        1000: ("hajar", "hazar", "hajaar", "hazaar", "thousand", "হাজার"),
        100000: ("lakh", "lac", "lakhs", "লাখ", "লক্ষ"),
    }
)
# "so" is also an English word, so "500 so" must not become 50000; only "pach so" counts.
_WORD_ONLY_MULTIPLIERS = {"so"}
# A multiplier that may stand alone at the start of an amount: "hajar taka dilo" = 1000.
_STANDALONE_MULTIPLIERS = {w for w, v in _MULTIPLIER.items() if v >= 1000}
_CURRENCY = {_nfc(w) for w in ("taka", "takar", "tk", "rs", "rupee", "rupees", "টাকা", "টাকার")}
# Multiplier suffixes that are often written joined: "pachsho", "পাঁচশো", "দেড়শ".
_JOINED_SUFFIXES = sorted(
    (w for w in _MULTIPLIER if w not in _WORD_ONLY_MULTIPLIERS), key=len, reverse=True
)

_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|[A-Za-zঀ-৿]+")
# "2,500" and Indian-style "1,25,000".
_THOUSANDS_SEP_RE = re.compile(r"(?<=\d),(?=\d{2,3}(?!\d))")
_NUMBER_RE = re.compile(r"\d+")


class _Token:
    __slots__ = ("start", "end", "text")

    def __init__(self, start: int, end: int, text: str) -> None:
        self.start, self.end, self.text = start, end, text


def _tokenize(text: str) -> list[_Token]:
    tokens = []
    for m in _TOKEN_RE.finditer(text):
        word = m.group().lower()
        tokens.extend(_Token(m.start(), m.end(), part) for part in _split_joined(word))
    return tokens


def _split_joined(word: str) -> list[str]:
    """'pachsho' -> ['pach', 'sho'], 'দেড়শো' -> ['দেড়', 'শো']; other words unchanged."""
    if word in _MULTIPLIER:
        return [word]
    for suffix in _JOINED_SUFFIXES:
        prefix = word.removesuffix(suffix)
        if prefix != word and (prefix in _BASE or prefix in _FRACTION):
            return [prefix, suffix]
    return [word]


def _base_value(text: str) -> float | None:
    if text in _BASE:
        return _BASE[text]
    if text[0].isdigit():
        return float(text)
    return None


def _parse_group(tokens: list[_Token], i: int, first: bool) -> tuple[float, int] | None:
    """One "<number> <multiplier>" group starting at tokens[i]: (value, index after it)."""
    n = len(tokens)
    text = tokens[i].text

    if text in _MODIFIERS and i + 1 < n and tokens[i + 1].text in _BASE:
        value, j = _BASE[tokens[i + 1].text] + _MODIFIERS[text], i + 2
    elif text in _FRACTION:
        value, j = _FRACTION[text], i + 1
    elif text in _MODIFIERS:
        return None
    elif first and text in _STANDALONE_MULTIPLIERS:
        return _MULTIPLIER[text], i + 1
    else:
        value = _base_value(text)
        if value is None:
            return None
        j = i + 1

    if j >= n or tokens[j].text not in _MULTIPLIER:
        return None
    if tokens[j].text in _WORD_ONLY_MULTIPLIERS and text[0].isdigit():
        return None
    return value * _MULTIPLIER[tokens[j].text], j + 1


def _parse_amount(tokens: list[_Token], i: int) -> tuple[float, int] | None:
    """A whole spoken amount starting at tokens[i], e.g. 'dui hajar pach sho ponchash'."""
    total, j = 0.0, i
    while j < len(tokens) and (group := _parse_group(tokens, j, first=j == i)):
        value, j = group
        total += value

    # A small number word either ends the amount ("dui hajar pach sho ponchash taka") or is
    # the whole amount ("bish taka"). Digits are left alone; they need no conversion.
    if j < len(tokens) and tokens[j].text in _BASE:
        next_text = tokens[j + 1].text if j + 1 < len(tokens) else None
        if next_text in _CURRENCY or (total and next_text is None):
            total += _BASE[tokens[j].text]
            j += 1

    if j == i or not total.is_integer():
        return None
    return total, j


def normalize_numbers(text: str) -> str:
    """Return the text with Bangla digits and spoken amounts written as plain digits."""
    text = _nfc(text).translate(_BANGLA_DIGITS)
    text = _THOUSANDS_SEP_RE.sub("", text)
    tokens = _tokenize(text)

    pieces: list[str] = []
    last_end = 0
    i = 0
    while i < len(tokens):
        parsed = _parse_amount(tokens, i)
        if parsed is None:
            i += 1
            continue
        value, j = parsed
        pieces.append(text[last_end : tokens[i].start])
        pieces.append(str(int(value)))
        last_end = tokens[j - 1].end
        i = j
    pieces.append(text[last_end:])
    return "".join(pieces)


def numbers_in(text: str) -> set[int]:
    """All whole numbers that appear in already-normalized text."""
    return {int(n) for n in _NUMBER_RE.findall(text)}
