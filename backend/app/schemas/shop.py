from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Name


class ShopCreate(BaseModel):
    name: Name
    owner_name: Name


class ShopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_name: str
    created_at: datetime
