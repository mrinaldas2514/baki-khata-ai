from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Name, Phone, ShortText


class CustomerCreate(BaseModel):
    name: Name
    phone: Phone = None
    note: ShortText = Field(
        default=None,
        description="Area or short note to tell apart customers with the same name",
        examples=["Bazar road"],
    )


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    name: str
    phone: str | None
    note: str | None
    created_at: datetime
    balance: int = Field(description="Total credit minus total payment, in taka")


class CustomerListItem(CustomerRead):
    owed_since: datetime | None = Field(
        description="Date of the oldest credit that is still unpaid; null when nothing is owed"
    )
