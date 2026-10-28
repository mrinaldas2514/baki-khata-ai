from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Name, Phone, ShortText


class CustomerCreate(BaseModel):
    name: Name
    phone: Phone = None
    note: ShortText = Field(
        default=None,
        description="Area or short note to tell apart customers with the same name",
        examples=["Bazar road"],
    )


class CustomerUpdate(BaseModel):
    """Partial update: only the fields sent are changed. Send null to clear phone/note."""

    name: Name | None = None
    phone: Phone = None
    note: ShortText = None

    @model_validator(mode="after")
    def _check_fields(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


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
