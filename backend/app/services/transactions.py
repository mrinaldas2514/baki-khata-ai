from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import Customer, Transaction
from app.schemas import (
    CustomerLedger,
    LedgerEntry,
    RecentTransaction,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
    TransactionWithBalance,
)
from app.services.balance import get_customer_balance, running_balance_sql
from app.services.customers import get_customer, to_customer_read
from app.services.exceptions import NotFoundError
from app.services.shops import get_shop
from app.time_utils import utc_now


def with_balance(db: Session, txn: Transaction) -> TransactionWithBalance:
    return TransactionWithBalance(
        **TransactionRead.model_validate(txn).model_dump(),
        customer_balance=get_customer_balance(db, txn.customer_id),
    )


def create_transaction(
    db: Session, shop_id: int, customer_id: int, data: TransactionCreate
) -> TransactionWithBalance:
    txn = add_transaction(db, get_customer(db, shop_id, customer_id), data)
    db.commit()
    db.refresh(txn)
    return with_balance(db, txn)


def add_transaction(db: Session, customer: Customer, data: TransactionCreate) -> Transaction:
    """Add a transaction for the customer to the session without committing."""
    values = data.model_dump()
    values["created_at"] = values["created_at"] or utc_now()
    txn = Transaction(shop_id=customer.shop_id, customer_id=customer.id, **values)
    db.add(txn)
    db.flush()
    return txn


def get_transaction(db: Session, shop_id: int, transaction_id: int) -> Transaction:
    get_shop(db, shop_id)
    txn = db.get(Transaction, transaction_id)
    if txn is None or txn.shop_id != shop_id:
        raise NotFoundError(f"Transaction {transaction_id} not found in shop {shop_id}")
    return txn


def get_transaction_with_balance(
    db: Session, shop_id: int, transaction_id: int
) -> TransactionWithBalance:
    return with_balance(db, get_transaction(db, shop_id, transaction_id))


def update_transaction(
    db: Session, shop_id: int, transaction_id: int, data: TransactionUpdate
) -> TransactionWithBalance:
    txn = get_transaction(db, shop_id, transaction_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return with_balance(db, txn)


def delete_transaction(db: Session, shop_id: int, transaction_id: int) -> None:
    txn = get_transaction(db, shop_id, transaction_id)
    db.delete(txn)
    db.commit()


def list_recent_transactions(db: Session, shop_id: int, limit: int) -> list[RecentTransaction]:
    """The shop's latest transactions across all customers, newest first."""
    get_shop(db, shop_id)
    stmt = (
        select(Transaction, Customer.name, Customer.note)
        .join(Customer, Customer.id == Transaction.customer_id)
        .where(Transaction.shop_id == shop_id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return [
        RecentTransaction(
            **TransactionRead.model_validate(txn).model_dump(),
            customer_name=name,
            customer_note=note,
        )
        for txn, name, note in db.execute(stmt)
    ]


def get_customer_ledger(
    db: Session,
    shop_id: int,
    customer_id: int,
    *,
    order: Literal["oldest", "newest"] = "oldest",
    limit: int | None = None,
    offset: int = 0,
) -> CustomerLedger:
    """A customer's transactions, each with the balance right after it.

    `order` and `limit`/`offset` pick a page; the running balance always counts the whole
    history, so the newest page of a long ledger shows the same numbers as the full list.
    """
    customer = get_customer(db, shop_id, customer_id)
    with_running = (
        select(Transaction, running_balance_sql().label("running_balance"))
        .where(Transaction.customer_id == customer.id)
        .subquery()
    )
    txn = aliased(Transaction, with_running)
    if order == "newest":
        sort = (txn.created_at.desc(), txn.id.desc())
    else:
        sort = (txn.created_at, txn.id)
    stmt = select(txn, with_running.c.running_balance).order_by(*sort).offset(offset).limit(limit)
    entries = [
        LedgerEntry(**TransactionRead.model_validate(t).model_dump(), running_balance=b)
        for t, b in db.execute(stmt)
    ]
    total = db.scalar(select(func.count()).where(Transaction.customer_id == customer.id))
    return CustomerLedger(
        customer=to_customer_read(customer, get_customer_balance(db, customer.id)),
        transactions=entries,
        total=total,
        has_more=offset + len(entries) < total,
    )
