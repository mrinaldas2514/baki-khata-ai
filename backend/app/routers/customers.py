from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CustomerCreate, CustomerRead
from app.services import customers as service

router = APIRouter(prefix="/shops/{shop_id}/customers", tags=["customers"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(shop_id: int, data: CustomerCreate, db: DB):
    customer = service.create_customer(db, shop_id, data)
    return service.to_customer_read(customer, balance=0)


@router.get("", response_model=list[CustomerRead])
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
