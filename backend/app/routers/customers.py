from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_shop_owner
from app.config import get_settings
from app.database import get_db
from app.llm import writing_llm_client
from app.schemas import CustomerCreate, CustomerListItem, CustomerRead, CustomerUpdate
from app.schemas.reminder import Reminder, ReminderRequest
from app.services import customers as service
from app.services import reminders

router = APIRouter(
    prefix="/shops/{shop_id}/customers",
    tags=["customers"],
    dependencies=[Depends(require_shop_owner)],
)
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


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(shop_id: int, customer_id: int, data: CustomerUpdate, db: DB):
    """Change the name, phone or area/note (only the fields you send)."""
    return service.update_customer(db, shop_id, customer_id, data)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(shop_id: int, customer_id: int, db: DB):
    """Only for a customer without any transactions (409 otherwise), e.g. after an undo."""
    service.delete_customer(db, shop_id, customer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{customer_id}/reminder", response_model=Reminder)
def create_reminder(
    request: Request,
    shop_id: int,
    customer_id: int,
    db: DB,
    user: CurrentUser,
    data: ReminderRequest | None = None,
):
    """A polite Banglish baki reminder to send on WhatsApp or copy. Nothing is sent or saved.

    409 if the customer doesn't owe anything.
    """
    settings = get_settings()
    polish = data.polish if data is not None else True
    llm = writing_llm_client(request, ai_enabled=user.ai_enabled) if polish else None
    return reminders.build_reminder(
        db,
        shop_id,
        customer_id,
        llm=llm,
        local_tz=settings.tz,
        country_code=settings.phone_country_code,
    )
