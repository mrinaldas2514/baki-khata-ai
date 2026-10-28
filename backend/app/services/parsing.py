"""Free-form sentence -> transaction preview -> (after the shopkeeper confirms) saved transaction.

    text --normalize numbers--> LLM --validate (retry once)--> ParsedTransaction
         --sanity checks + customer name matching--> ParsePreview

Nothing is written to the database until `confirm` is called.
"""

import json
import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.llm import ChatMessage, LLMClient
from app.schemas import (
    CustomerCandidate,
    CustomerMatchResult,
    CustomerRead,
    ParseConfirm,
    ParseConfirmResult,
    ParsedTransaction,
    ParsePreview,
    TransactionCreate,
)
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


def _validate(answer: str) -> ParsedTransaction:
    data = json.loads(_strip_code_fence(answer))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    if data.get("error") and data.get("amount") is None:
        raise NotATransactionError(
            f"Could not find a transaction in this sentence: {data['error']}"
        )
    return ParsedTransaction.model_validate(data)


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
    """Parse the sentence and find the customer. Saves nothing."""
    get_shop(db, shop_id)  # 404 before spending an LLM call
    parsed, warnings = _sanity_check(raw_text, parse_with_llm(llm, raw_text))
    match = _match_customer(db, shop_id, parsed.customer_name)
    if match.status == MatchStatus.FUZZY:
        warnings.append(
            f"'{parsed.customer_name}' was matched to {match.customer.name}. Please check it."
        )
    return ParsePreview(raw_text=raw_text, parsed=parsed, match=match, warnings=warnings)


def confirm(db: Session, shop_id: int, data: ParseConfirm) -> ParseConfirmResult:
    """Save the confirmed entry, creating the customer first if needed, in one commit."""
    if data.customer_id is not None:
        customer = customer_service.get_customer(db, shop_id, data.customer_id)
    else:
        customer = customer_service.add_customer(db, shop_id, data.new_customer)
    txn_data = TransactionCreate(
        type=data.type,
        amount=data.amount,
        item=data.item,
        raw_text=data.raw_text,
        created_at=data.created_at,
    )
    txn = transaction_service.add_transaction(db, customer, txn_data)
    db.commit()
    transaction = transaction_service.with_balance(db, txn)
    return ParseConfirmResult(
        transaction=transaction,
        customer=customer_service.to_customer_read(customer, transaction.customer_balance),
        customer_created=data.new_customer is not None,
    )
