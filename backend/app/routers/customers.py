from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.llm import LLMClient, get_writing_llm_client
from app.schemas import CustomerCreate, CustomerListItem, CustomerRead
from app.schemas.reminder import Reminder, ReminderRequest
from app.services import customers as service
from app.services import reminders

router = APIRouter(prefix="/shops/{shop_id}/customers", tags=["customers"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(shop_id: int, data: CustomerCreate, db: DB):
    customer = service.create_customer(db, shop_id, data)
    return service.to_customer_read(customer, balance=0)


@router.get("", response_model=list[CustomerListItem])
def list_customers(
    shop_id: int,
    db: DB,
    search: Annotated[
        str | None, Query(max_length=100, description="Match name, note or phone")
    ] = None,
):
    return service.list_customers(db, shop_id, search)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(shop_id: int, customer_id: int, db: DB):
    return service.get_customer_with_balance(db, shop_id, customer_id)


@router.post("/{customer_id}/reminder", response_model=Reminder)
def create_reminder(
    shop_id: int,
    customer_id: int,
    db: DB,
    llm: Annotated[LLMClient | None, Depends(get_writing_llm_client)],
    data: ReminderRequest | None = None,
):
    """A polite Banglish baki reminder to send on WhatsApp or copy. Nothing is sent or saved.

    409 if the customer doesn't owe anything.
    """
    settings = get_settings()
    polish = data.polish if data is not None else True
    return reminders.build_reminder(
        db,
        shop_id,
        customer_id,
        llm=llm if polish else None,
        local_tz=settings.tz,
        country_code=settings.phone_country_code,
    )
