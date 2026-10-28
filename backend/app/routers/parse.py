from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_shop_owner
from app.database import get_db
from app.llm import parsing_llm_client
from app.rate_limit import check_rate
from app.schemas import ParseConfirm, ParseConfirmResult, ParsePreview, ParseRequest
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


@router.post("/confirm", response_model=ParseConfirmResult, status_code=status.HTTP_201_CREATED)
def confirm_parsed(shop_id: int, data: ParseConfirm, db: DB):
    """Save the confirmed (possibly edited) preview, creating the customer if new."""
    return service.confirm(db, shop_id, data)
