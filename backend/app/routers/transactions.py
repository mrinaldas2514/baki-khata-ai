from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CustomerLedger,
    RecentTransaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionWithBalance,
)
from app.services import transactions as service

router = APIRouter(prefix="/shops/{shop_id}", tags=["transactions"])
DB = Annotated[Session, Depends(get_db)]


@router.post(
    "/customers/{customer_id}/transactions",
    response_model=TransactionWithBalance,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(shop_id: int, customer_id: int, data: TransactionCreate, db: DB):
    return service.create_transaction(db, shop_id, customer_id, data)


@router.get("/customers/{customer_id}/transactions", response_model=CustomerLedger)
def list_customer_transactions(
    shop_id: int,
    customer_id: int,
    db: DB,
    order: Annotated[
        Literal["oldest", "newest"], Query(description="oldest first (default) or newest first")
    ] = "oldest",
    limit: Annotated[
        int | None, Query(ge=1, le=200, description="Page size. Leave out for all of them.")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="How many to skip")] = 0,
):
    """The customer's khata with a running balance. Page through it with limit/offset."""
    return service.get_customer_ledger(
        db, shop_id, customer_id, order=order, limit=limit, offset=offset
    )


@router.get("/transactions", response_model=list[RecentTransaction])
def list_recent_transactions(shop_id: int, db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 10):
    """The shop's latest transactions across all customers, newest first."""
    return service.list_recent_transactions(db, shop_id, limit)


@router.get("/transactions/{transaction_id}", response_model=TransactionWithBalance)
def get_transaction(shop_id: int, transaction_id: int, db: DB):
    return service.get_transaction_with_balance(db, shop_id, transaction_id)


@router.patch("/transactions/{transaction_id}", response_model=TransactionWithBalance)
def update_transaction(shop_id: int, transaction_id: int, data: TransactionUpdate, db: DB):
    return service.update_transaction(db, shop_id, transaction_id, data)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(shop_id: int, transaction_id: int, db: DB):
    service.delete_transaction(db, shop_id, transaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
