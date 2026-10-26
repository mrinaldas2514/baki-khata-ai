from sqlalchemy.orm import Session

from app.models import Shop
from app.schemas import ShopCreate
from app.services.exceptions import NotFoundError


def create_shop(db: Session, data: ShopCreate) -> Shop:
    shop = Shop(**data.model_dump())
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


def get_shop(db: Session, shop_id: int) -> Shop:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise NotFoundError(f"Shop {shop_id} not found")
    return shop
