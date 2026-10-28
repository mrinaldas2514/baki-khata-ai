"""Free-form sentence -> transaction preview -> (after the shopkeeper confirms) saved transaction.

    text --normalize numbers--> LLM --validate (retry once)--> ParsedTransaction (one or more)
         --sanity checks + customer name matching--> ParsePreview

Nothing is written to the database until `confirm` (or `confirm_many`) is called.
"""

import json
import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.llm import ChatMessage, LLMClient
from app.models import Customer
from app.schemas import (
    CustomerCandidate,
    CustomerMatchResult,
    CustomerRead,
    EntryPreview,
    ParseConfirm,
    ParseConfirmMany,
    ParseConfirmManyResult,
    ParseConfirmResult,
    ParsedTransaction,
    ParsePreview,
    TransactionCreate,
)
from app.schemas.parse import MAX_ENTRIES
from app.services import customers as customer_service
from app.services import transactions as transaction_service
from app.services.name_matching import MatchStatus, clean_name, match_name
from app.services.number_words import normalize_numbers, numbers_in
from app.services.parse_prompt import RETRY_PROMPT, SYSTEM_PROMPT, user_prompt
from app.services.shops import get_shop

logger = logging.getLogger(__name__)

# The most an unverified amount is trusted (see `_sanity_check`).
UNVERIFIED_AMOUNT_CONFIDENCE = 0.5


class LLMOutputError(Exception):
    """The model's answer was still not valid after one retry."""


class NotATransactionError(Exception):
    """The model understood the sentence, but it has no customer name or amount."""


def parse_with_llm(llm: LLMClient, raw_text: str) -> ParsedTransaction:
    """The sentence's (first) entry. See `parse_entries_with_llm`."""
    return parse_entries_with_llm(llm, raw_text)[0]


def parse_entries_with_llm(llm: LLMClient, raw_text: str) -> list[ParsedTransaction]:
    """Ask the model, validate its JSON, and retry once (telling it what was wrong)."""
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(raw_text, normalize_numbers(raw_text))},
    ]
    problem = ""
    for attempt in (1, 2):
        answer = llm.complete_json(messages)
        try:
            return _validate(answer)
        except (ValueError, ValidationError) as exc:
            problem = _describe(exc)
            # The answer holds the customer's name and amount: only at DEBUG, never at INFO+.
            logger.warning("Invalid LLM answer (attempt %d): %s", attempt, type(exc).__name__)
            logger.debug("Invalid LLM answer (attempt %d): %s | %r", attempt, problem, answer)
            messages += [
                {"role": "assistant", "content": answer},
                {"role": "user", "content": RETRY_PROMPT.format(problem=problem)},
            ]
    raise LLMOutputError(
        "The AI could not read this sentence (it gave an invalid answer twice). "
        f"Please try again or enter the transaction manually. Last problem: {problem}"
    )


def _validate(answer: str) -> list[ParsedTransaction]:
    data = json.loads(_strip_code_fence(answer))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    if data.get("error") and data.get("amount") is None and not data.get("entries"):
        raise NotATransactionError(
            f"Could not find a transaction in this sentence: {data['error']}"
        )
    if "entries" not in data:
        # A single entry without the list around it: fine too.
        return [ParsedTransaction.model_validate(data)]
    entries = data["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError(f"entries must be a list of 1 to {MAX_ENTRIES} objects")
    parsed = []
    for i, entry in enumerate(entries):
        try:
            parsed.append(ParsedTransaction.model_validate(entry))
        except ValidationError as exc:
            raise ValueError(f"entries.{i}: {_describe(exc)}") from exc
    return parsed


def _strip_code_fence(answer: str) -> str:
    """Some models wrap JSON in ```json ... ``` even in JSON mode."""
    text = answer.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```")
    return text.strip()


def _describe(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return f"not valid JSON ({exc.msg})"
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'answer'}: {err['msg']}"
            for err in exc.errors()
        )
    return str(exc)


def _sanity_check(raw_text: str, parsed: ParsedTransaction) -> tuple[ParsedTransaction, list[str]]:
    """Catch answers the model made up: the amount must appear in the sentence."""
    warnings = []
    if parsed.amount not in numbers_in(normalize_numbers(raw_text)):
        warnings.append(
            f"The amount {parsed.amount} was not found in the sentence. Please check it."
        )
        confidence = min(parsed.confidence, UNVERIFIED_AMOUNT_CONFIDENCE)
        parsed = parsed.model_copy(update={"confidence": confidence})
    return parsed, warnings


def _match_customer(db: Session, shop_id: int, name: str) -> CustomerMatchResult:
    customers = customer_service.list_customers(db, shop_id)
    result = match_name(name, customers)

    def candidate(customer: CustomerRead, score: int) -> CustomerCandidate:
        return CustomerCandidate(**customer.model_dump(), score=score)

    candidates = [candidate(c, score) for c, score in result.candidates]
    chosen = next((c for c in candidates if result.match and c.id == result.match.id), None)
    return CustomerMatchResult(
        status=result.status,
        customer=chosen,
        candidates=candidates,
        suggested_name=clean_name(name),
    )


def preview(db: Session, llm: LLMClient, shop_id: int, raw_text: str) -> ParsePreview:
    """Parse the sentence and find each entry's customer. Saves nothing."""
    get_shop(db, shop_id)  # 404 before spending an LLM call
    entries = []
    for parsed in parse_entries_with_llm(llm, raw_text):
        parsed, warnings = _sanity_check(raw_text, parsed)
        match = _match_customer(db, shop_id, parsed.customer_name)
        if match.status == MatchStatus.FUZZY:
            warnings.append(
                f"'{parsed.customer_name}' was matched to {match.customer.name}. Please check it."
            )
        entries.append(EntryPreview(parsed=parsed, match=match, warnings=warnings))
    first = entries[0]
    return ParsePreview(
        raw_text=raw_text,
        parsed=first.parsed,
        match=first.match,
        warnings=first.warnings,
        entries=entries,
        parser=llm.parser,
        model=llm.model,
    )


def confirm(db: Session, shop_id: int, data: ParseConfirm) -> ParseConfirmResult:
    """Save the confirmed entry, creating the customer first if needed, in one commit."""
    return confirm_many(db, shop_id, ParseConfirmMany(entries=[data])).results[0]


def confirm_many(db: Session, shop_id: int, data: ParseConfirmMany) -> ParseConfirmManyResult:
    """Save several confirmed entries in one commit: all of them, or (on any error) none.

    Two entries for the same new customer ("tanvir 50 baki, tanvir 20 dilo") create them once.
    """
    created: dict[tuple[str, str], Customer] = {}
    saved = []
    for entry in data.entries:
        is_new = False
        if entry.customer_id is not None:
            customer = customer_service.get_customer(db, shop_id, entry.customer_id)
        else:
            new = entry.new_customer
            key = (new.name.lower(), (new.note or "").lower())
            customer = created.get(key)
            if customer is None:
                customer = customer_service.add_customer(db, shop_id, new)
                created[key] = customer
                is_new = True
        txn_data = TransactionCreate(
            type=entry.type,
            amount=entry.amount,
            item=entry.item,
            raw_text=entry.raw_text,
            created_at=entry.created_at,
        )
        txn = transaction_service.add_transaction(db, customer, txn_data)
        saved.append((txn, customer, is_new))
    db.commit()
    results = []
    for txn, customer, is_new in saved:
        transaction = transaction_service.with_balance(db, txn)
        results.append(
            ParseConfirmResult(
                transaction=transaction,
                customer=customer_service.to_customer_read(customer, transaction.customer_balance),
                customer_created=is_new,
            )
        )
    logger.info("Saved %d entries in shop %d", len(results), shop_id)
    return ParseConfirmManyResult(results=results)
