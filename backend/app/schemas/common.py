"""Reusable validated field types."""

import re
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints

from app.config import get_settings
from app.services.phones import normalize_mobile
from app.time_utils import to_utc, utc_now

MAX_AMOUNT = 10_000_000  # 1 crore taka; anything bigger in a single entry is almost surely a typo.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _check_amount(value: int) -> int:
    if value <= 0:
        raise ValueError("Amount must be greater than 0")
    if value > MAX_AMOUNT:
        raise ValueError(f"Amount must not be more than {MAX_AMOUNT} taka")
    return value


def _check_phone(value: str | None) -> str | None:
    """Bangladesh or India mobile, stored as +8801XXXXXXXXX / +91XXXXXXXXXX."""
    return None if value is None else normalize_mobile(value)


def _check_email(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address")
    return value


def _normalize_timestamp(value: datetime) -> datetime:
    value = to_utc(value, get_settings().tz)
    # Small allowance for clock differences between the phone and the server.
    if value > utc_now() + timedelta(minutes=5):
        raise ValueError("Date cannot be in the future")
    return value


# Required text: whitespace is trimmed and an empty value is rejected.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# Optional text: whitespace is trimmed and an empty string becomes null.
ShortText = Annotated[Annotated[str, Field(max_length=200)] | None, BeforeValidator(_blank_to_none)]
LongText = Annotated[Annotated[str, Field(max_length=2000)] | None, BeforeValidator(_blank_to_none)]
Phone = Annotated[
    Annotated[str, Field(max_length=30)] | None,
    BeforeValidator(_blank_to_none),
    AfterValidator(_check_phone),
]
Email = Annotated[
    Annotated[str, Field(max_length=254)] | None,
    BeforeValidator(_blank_to_none),
    AfterValidator(_check_email),
]

# Whole taka, strictly an integer (so 10.5, "100" and true are rejected).
Amount = Annotated[int, Field(strict=True), AfterValidator(_check_amount)]

# Naive datetimes are treated as the shop's local time; stored as UTC.
PastDateTime = Annotated[datetime, AfterValidator(_normalize_timestamp)]
