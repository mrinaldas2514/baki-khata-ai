from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm import LLMClient, get_llm_client
from app.schemas import ParseConfirm, ParseConfirmResult, ParsePreview, ParseRequest
from app.services import parsing as service

router = APIRouter(prefix="/shops/{shop_id}/parse", tags=["ai parsing"])
DB = Annotated[Session, Depends(get_db)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]


@router.post("", response_model=ParsePreview)
def parse_text(shop_id: int, data: ParseRequest, db: DB, llm: LLM):
    """Turn one free-form sentence into a transaction preview. Nothing is saved."""
    return service.preview(db, llm, shop_id, data.text)


@router.post("/confirm", response_model=ParseConfirmResult, status_code=status.HTTP_201_CREATED)
def confirm_parsed(shop_id: int, data: ParseConfirm, db: DB):
    """Save the confirmed (possibly edited) preview, creating the customer if new."""
    return service.confirm(db, shop_id, data)
