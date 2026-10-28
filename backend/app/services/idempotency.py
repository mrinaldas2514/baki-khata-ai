"""Saving with an Idempotency-Key: a request sent again gets the first answer, not a second save.

The app's offline queue retries a save until it hears back, and on a weak connection the first
try may have been saved even though its answer never arrived. Each save carries a random key;
the answer is stored with the shop and key in the same commit as the entries, so either both
are saved or neither is.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import timedelta

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKey
from app.services.exceptions import ConflictError
from app.time_utils import utc_now

KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,100}$")
# Long enough for any phone to come back online; then the key may be forgotten.
KEEP_FOR = timedelta(days=30)
REPLAYED_HEADER = "Idempotent-Replayed"


class KeyReusedError(ConflictError):
    pass


def fingerprint(endpoint: str, data: BaseModel) -> str:
    body = json.dumps(data.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{endpoint}\n{body}".encode()).hexdigest()


def _find(db: Session, shop_id: int, key: str) -> IdempotencyKey | None:
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.shop_id == shop_id, IdempotencyKey.key == key
    )
    return db.scalar(stmt)


def _replay(stored: IdempotencyKey, request_hash: str) -> JSONResponse:
    if stored.request_hash != request_hash:
        raise KeyReusedError(
            "This Idempotency-Key was already used for a different request. "
            "Use a new key for every save."
        )
    return JSONResponse(
        status_code=stored.status_code,
        content=json.loads(stored.response),
        headers={REPLAYED_HEADER: "true"},
    )


def run_once(
    db: Session,
    shop_id: int,
    key: str | None,
    request_hash: str,
    save: Callable[[Callable[[BaseModel], None]], BaseModel],
    *,
    status_code: int,
):
    """Call `save(remember)` once per key. `save` must call `remember(answer)` before it commits.

    Without a key it just saves. With a key used before (same request) it answers what it
    answered then; two requests with the same key at once save once (the unique key decides).
    """
    if key is None:
        return save(lambda _answer: None)
    if (stored := _find(db, shop_id, key)) is not None:
        return _replay(stored, request_hash)

    def remember(answer: BaseModel) -> None:
        cutoff = utc_now() - KEEP_FOR
        db.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.shop_id == shop_id, IdempotencyKey.created_at < cutoff
            )
        )
        db.add(
            IdempotencyKey(
                shop_id=shop_id,
                key=key,
                request_hash=request_hash,
                status_code=status_code,
                response=answer.model_dump_json(),
            )
        )

    try:
        return save(remember)
    except (IntegrityError, ConflictError):
        # Another request with this key may have committed meanwhile: the unique key stops
        # this one at its commit, or its own new customer already exists ("Tanvir exists").
        # Then answer what that one saved; otherwise it's a real error.
        db.rollback()
        if (stored := _find(db, shop_id, key)) is not None:
            return _replay(stored, request_hash)
        raise
