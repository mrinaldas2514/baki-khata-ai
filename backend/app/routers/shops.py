from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ShopCreate, ShopRead
from app.services import shops as service

router = APIRouter(prefix="/shops", tags=["shops"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ShopRead, status_code=status.HTTP_201_CREATED)
def create_shop(data: ShopCreate, db: DB):
    return service.create_shop(db, data)


@router.get("/{shop_id}", response_model=ShopRead)
def get_shop(shop_id: int, db: DB):
    return service.get_shop(db, shop_id)
