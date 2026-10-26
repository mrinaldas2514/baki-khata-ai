from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.models import TransactionType
from app.schemas.common import Amount, Name, PastDateTime, ShortText
from app.schemas.customer import CustomerCreate, CustomerRead
from app.schemas.transaction import TransactionWithBalance
from app.services.name_matching import MatchStatus


def _whole_float_to_int(value: object) -> object:
    # Models sometimes write 500 as 500.0; that is still a whole number of taka.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


class ParsedTransaction(BaseModel):
    """What the LLM must return. Anything that doesn't fit is rejected and retried once."""

    customer_name: Name
    amount: Annotated[Amount, BeforeValidator(_whole_float_to_int)]
    type: TransactionType
    item: ShortText = None
    confidence: float = Field(ge=0, le=1, description="0 to 1: how sure the AI is")


class ParseRequest(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = (
        Field(examples=["rahim bhai 2 kg chal 120 taka baki"])
    )


class CustomerCandidate(CustomerRead):
    score: int = Field(ge=0, le=100, description="Name similarity, 100 = same name")


class CustomerMatchResult(BaseModel):
    status: MatchStatus = Field(
        description="exact / fuzzy: `customer` is the match. ambiguous: pick from `candidates`. "
        "new: no similar customer, create `suggested_name`."
    )
    customer: CustomerCandidate | None = Field(description="The matched customer, if decided")
    candidates: list[CustomerCandidate] = Field(description="Similar customers, closest first")
    suggested_name: str = Field(description="Cleaned name to use if this is a new customer")


class ParsePreview(BaseModel):
    """Nothing is saved yet. Show this to the shopkeeper, then call /parse/confirm."""

    raw_text: str
    parsed: ParsedTransaction
    match: CustomerMatchResult
    warnings: list[str] = Field(description="Things the shopkeeper should double-check")


class ParseConfirm(BaseModel):
    """The (possibly edited) preview. Give either `customer_id` or `new_customer`."""

    raw_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    type: TransactionType
    amount: Amount
    item: ShortText = None
    created_at: PastDateTime | None = Field(
        default=None,
        description="When it happened. Defaults to now. Naive values are read as the shop's local time.",
    )
    customer_id: int | None = Field(default=None, description="An existing customer")
    new_customer: CustomerCreate | None = Field(default=None, description="Create this customer")

    @model_validator(mode="after")
    def _one_customer(self) -> "ParseConfirm":
        if (self.customer_id is None) == (self.new_customer is None):
            raise ValueError("Give exactly one of customer_id or new_customer")
        return self


class ParseConfirmResult(BaseModel):
    transaction: TransactionWithBalance
    customer: CustomerRead = Field(description="The customer, with the balance after this entry")
    customer_created: bool
