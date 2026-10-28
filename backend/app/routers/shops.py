from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_shop_owner
from app.database import get_db
from app.schemas import ShopRead
from app.services import shops as service

# Shops are created together with their owner's account: POST /auth/register.
router = APIRouter(prefix="/shops", tags=["shops"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/{shop_id}", response_model=ShopRead, dependencies=[Depends(require_shop_owner)])
def get_shop(shop_id: int, db: DB):
    return service.get_shop(db, shop_id)
