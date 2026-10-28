"""Mobile numbers from Bangladesh and India, stored in one international form (E.164).

    01711-000001, 01711000001, +880 1711 000001, 8801711000001, 008801711000001
        -> +8801711000001
    +91 98765 43210, 919876543210, 09876543210, 98765 43210
        -> +919876543210

Bangladesh mobiles are 01 + operator digit 3-9 + 8 digits. Indian mobiles are 10 digits
starting with 6-9. The two never look alike, so a number without a country code can be
told apart: 01... is Bangladesh, 6-9... (or 06-09...) is India.
"""

import re

_BD = re.compile(r"1[3-9]\d{8}")  # after +880 or the leading 0
_IN = re.compile(r"[6-9]\d{9}")  # after +91 or the leading 0
_ALLOWED = re.compile(r"^\+?[\d\s\-().]+$")

INVALID_PHONE = (
    "Enter a Bangladesh mobile number (01XXXXXXXXX or +880...) or an Indian one (+91...), "
    "digits only"
)


def normalize_mobile(text: str) -> str:
    """The number as +8801XXXXXXXXX or +91XXXXXXXXXX. ValueError if it isn't a BD/IN mobile."""
    text = text.strip()
    if not _ALLOWED.match(text):
        raise ValueError(INVALID_PHONE)
    digits = re.sub(r"\D", "", text)
    international = text.startswith("+") or digits.startswith("00")
    if digits.startswith("00"):
        digits = digits[2:]

    if international or len(digits) in (12, 13):
        if digits.startswith("880") and _BD.fullmatch(digits[3:]):
            return "+880" + digits[3:]
        if digits.startswith("91") and _IN.fullmatch(digits[2:]):
            return "+91" + digits[2:]
        if international:
            raise ValueError(INVALID_PHONE)

    local = digits.removeprefix("0")
    if _BD.fullmatch(local):
        return "+880" + local
    if _IN.fullmatch(local):
        return "+91" + local
    raise ValueError(INVALID_PHONE)
