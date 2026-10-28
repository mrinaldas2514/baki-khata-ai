from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.llm.base import ParserKind
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


class EntryPreview(BaseModel):
    """One entry the sentence was understood as."""

    parsed: ParsedTransaction
    match: CustomerMatchResult
    warnings: list[str] = Field(description="Things the shopkeeper should double-check")


class ParsePreview(EntryPreview):
    """Nothing is saved yet. Show this to the shopkeeper, then call /parse/confirm.

    `parsed`, `match` and `warnings` are the first entry. A sentence about several customers
    ("rahim 200 baki, karim 500 dilo") has one item per customer in `entries` (save them with
    /parse/confirm-many); a usual sentence has exactly one, the same as the top-level fields.
    """

    raw_text: str
    entries: list[EntryPreview] = Field(description="Every entry, in the order written")
    parser: ParserKind = Field(
        description='"llm": read by the AI model. "rules": read by the simple rule-based parser '
        "(AI turned off in Settings, or no AI key on the server)."
    )
    model: str = Field(description='The model id, e.g. "openai/gpt-oss-120b", or "rule-based"')


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


MAX_ENTRIES = 10


class ParseConfirmMany(BaseModel):
    """Several confirmed entries from one sentence, saved together (all or nothing)."""

    entries: list[ParseConfirm] = Field(min_length=1, max_length=MAX_ENTRIES)


class ParseConfirmManyResult(BaseModel):
    results: list[ParseConfirmResult] = Field(
        description="In the same order. Balances are each customer's balance after all of them."
    )
