"""Baki reminder messages the shopkeeper can send a customer on WhatsApp (or copy).

The message always starts from a fixed, polite Banglish template, so it works without AI.
When an AI model is set up it may reword the template to sound more natural, but its version
is only used if it keeps the customer's name and amount and adds no numbers of its own;
otherwise the template is used. The server never sends anything: the app opens WhatsApp with
the text filled in and the shopkeeper presses send.
"""

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.llm import ChatMessage, LLMClient, LLMProviderError
from app.schemas.reminder import Reminder
from app.services.balance import get_customer_balance, get_owed_since
from app.services.customers import get_customer
from app.services.exceptions import ConflictError
from app.services.shops import get_shop

logger = logging.getLogger(__name__)

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
MAX_MESSAGE_LENGTH = 600


def format_amount(amount: int) -> str:
    """South Asian digit grouping, as on the app: 125000 -> '1,25,000'."""
    digits = str(amount)
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *groups, tail])


def format_day(when: datetime, local_tz: ZoneInfo) -> str:
    """'12 October', in the shop's local time."""
    local = when.astimezone(local_tz)
    return f"{local.day} {_MONTHS[local.month - 1]}"


def template_message(
    *, name: str, amount: int, shop_name: str, owner_name: str, since: str | None
) -> str:
    since_text = f" ({since} theke)" if since else ""
    return (
        f"Priyo {name},\n"
        f"Ashakori bhalo achen. {shop_name}-e apnar {format_amount(amount)} taka baki ache"
        f"{since_text}.\n"
        "Shubidha moto shodh kore dile khub upokar hoy.\n"
        f"Dhonnobad,\n{owner_name}, {shop_name}"
    )


def whatsapp_number(phone: str | None, country_code: str) -> str | None:
    """'01711-000001' -> '8801711000001' (digits only, as wa.me wants). None if unusable.

    Numbers written with + or 00 are already international. A leading 0 is the local trunk
    prefix and is replaced by the country code; a number without either gets it in front.
    """
    if not phone:
        return None
    text = phone.strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        number = digits
    elif digits.startswith("00"):
        number = digits[2:]
    elif digits.startswith(country_code) and len(digits) > 10:
        number = digits
    elif digits.startswith("0"):
        number = country_code + digits[1:]
    else:
        number = country_code + digits
    # E.164 allows at most 15 digits; a mobile number with its country code is at least 10.
    return number if 10 <= len(number) <= 15 else None


_POLISH_PROMPT = """\
You reword a short payment reminder that a small shopkeeper in Bangladesh or India sends a \
customer on WhatsApp. Write it in friendly, polite, respectful Banglish (Bangla written in \
English letters), the way a shopkeeper would talk to a regular customer they like.

Rules:
- Keep the customer's name exactly as given.
- Keep the amount exactly as given (for example "1,200 taka"). Do not add any other numbers.
- Keep the date if one is given. Keep the shop's and owner's names at the end.
- Be warm and short (at most 5 short lines). No threats, no guilt, no pressure, no new facts.
- Answer with exactly one JSON object: {"message": "<the reworded reminder>"}"""


class _PolishedMessage(BaseModel):
    message: str = Field(min_length=20, max_length=MAX_MESSAGE_LENGTH)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\d|\d", text)}


def _polish(llm: LLMClient, template: str, name: str, amount: int) -> str | None:
    """The AI's rewording, or None if it failed or changed the facts."""
    messages: list[ChatMessage] = [
        {"role": "system", "content": _POLISH_PROMPT},
        {"role": "user", "content": template},
    ]
    try:
        raw = llm.complete_json(messages)
        polished = _PolishedMessage.model_validate(json.loads(raw)).message.strip()
    except (LLMProviderError, ValueError, ValidationError, TypeError) as exc:
        logger.warning("Reminder polish failed, using the template: %s", exc)
        return None
    if name.lower() not in polished.lower():
        logger.warning("Reminder polish dropped the customer's name, using the template")
        return None
    if str(amount) not in _numbers(polished) or not _numbers(polished) <= _numbers(template):
        logger.warning("Reminder polish changed the numbers, using the template")
        return None
    return polished


def build_reminder(
    db: Session,
    shop_id: int,
    customer_id: int,
    *,
    llm: LLMClient | None,
    local_tz: ZoneInfo,
    country_code: str,
) -> Reminder:
    """A reminder for the customer's current baki. 409 if they don't owe anything."""
    customer = get_customer(db, shop_id, customer_id)
    balance = get_customer_balance(db, customer.id)
    if balance <= 0:
        raise ConflictError(f"Customer {customer_id} has no baki to remind about")
    owed_since = get_owed_since(db, [customer.id]).get(customer.id)
    shop = get_shop(db, shop_id)
    template = template_message(
        name=customer.name,
        amount=balance,
        shop_name=shop.name,
        owner_name=shop.owner_name,
        since=format_day(owed_since, local_tz) if owed_since else None,
    )
    polished = _polish(llm, template, customer.name, balance) if llm is not None else None
    return Reminder(
        message=polished or template,
        polished=polished is not None,
        phone=customer.phone,
        whatsapp_number=whatsapp_number(customer.phone, country_code),
    )
