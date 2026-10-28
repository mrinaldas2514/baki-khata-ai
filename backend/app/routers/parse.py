from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_shop_owner
from app.database import get_db
from app.llm import parsing_llm_client
from app.rate_limit import check_rate
from app.schemas import (
    ParseConfirm,
    ParseConfirmMany,
    ParseConfirmManyResult,
    ParseConfirmResult,
    ParsePreview,
    ParseRequest,
)
from app.services import idempotency
from app.services import parsing as service

router = APIRouter(
    prefix="/shops/{shop_id}/parse", tags=["ai parsing"], dependencies=[Depends(require_shop_owner)]
)
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ParsePreview)
def parse_text(request: Request, shop_id: int, data: ParseRequest, db: DB, user: CurrentUser):
    """Turn one free-form sentence into a transaction preview. Nothing is saved.

    With AI turned off in the settings, the rule-based parser reads it instead and nothing is
    sent to the AI provider.
    """
    check_rate(request, "parse", f"shop:{shop_id}")
    llm = parsing_llm_client(request, ai_enabled=user.ai_enabled)
    return service.preview(db, llm, shop_id, data.text)


IdempotencyKeyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        pattern=idempotency.KEY_RE.pattern,
        description="A random key per save (8-100 letters, digits, - _ . :). Sending the same "
        "save again with it answers the first result (header Idempotent-Replayed: true) "
        "instead of saving twice; the same key with other data is 409.",
    ),
]


@router.post("/confirm", response_model=ParseConfirmResult, status_code=status.HTTP_201_CREATED)
def confirm_parsed(shop_id: int, data: ParseConfirm, db: DB, key: IdempotencyKeyHeader = None):
    """Save the confirmed (possibly edited) preview, creating the customer if new."""
    return idempotency.run_once(
        db,
        shop_id,
        key,
        idempotency.fingerprint("confirm", data),
        lambda remember: service.confirm(db, shop_id, data, remember),
        status_code=status.HTTP_201_CREATED,
    )


@router.post(
    "/confirm-many", response_model=ParseConfirmManyResult, status_code=status.HTTP_201_CREATED
)
def confirm_many(shop_id: int, data: ParseConfirmMany, db: DB, key: IdempotencyKeyHeader = None):
    """Save every entry of a sentence about several customers, together (all or nothing).

    The app's offline queue sends its saved entries here, each with its Idempotency-Key.
    """
    return idempotency.run_once(
        db,
        shop_id,
        key,
        idempotency.fingerprint("confirm-many", data),
        lambda remember: service.confirm_many(db, shop_id, data, remember),
        status_code=status.HTTP_201_CREATED,
    )
