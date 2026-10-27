from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import TransactionType
from app.schemas.common import Amount, LongText, PastDateTime, ShortText
from app.schemas.customer import CustomerRead


class TransactionCreate(BaseModel):
    type: TransactionType
    amount: Amount
    item: ShortText = None
    raw_text: LongText = None
    created_at: PastDateTime | None = Field(
        default=None,
        description="When it happened. Defaults to now. Naive values are read as the shop's local time.",
    )


class TransactionUpdate(BaseModel):
    """Partial update: only the fields sent are changed. Send null to clear item/raw_text."""

    type: TransactionType | None = None
    amount: Amount | None = None
    item: ShortText = None
    raw_text: LongText = None
    created_at: PastDateTime | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "TransactionUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for field in ("type", "amount", "created_at"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    customer_id: int
    type: TransactionType
    amount: int
    item: str | None
    raw_text: str | None
    created_at: datetime


class TransactionWithBalance(TransactionRead):
    customer_balance: int = Field(description="Customer's balance after this change")


class RecentTransaction(TransactionRead):
    customer_name: str
    customer_note: str | None


class LedgerEntry(TransactionRead):
    running_balance: int = Field(description="Customer's balance right after this transaction")


class CustomerLedger(BaseModel):
    customer: CustomerRead
    transactions: list[LedgerEntry] = Field(description="Oldest first")
