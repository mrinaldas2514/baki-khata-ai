from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction
from app.schemas import (
    CustomerLedger,
    LedgerEntry,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
    TransactionWithBalance,
)
from app.services.balance import get_customer_balance, running_balances
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


def get_customer_ledger(db: Session, shop_id: int, customer_id: int) -> CustomerLedger:
    """A customer's transactions, oldest first, each with the balance right after it."""
    customer = get_customer(db, shop_id, customer_id)
    stmt = (
        select(Transaction)
        .where(Transaction.customer_id == customer.id)
        .order_by(Transaction.created_at, Transaction.id)
    )
    txns = list(db.scalars(stmt))
    balances = running_balances(txns)
    entries = [
        LedgerEntry(**TransactionRead.model_validate(t).model_dump(), running_balance=b)
        for t, b in zip(txns, balances, strict=True)
    ]
    final_balance = balances[-1] if balances else 0
    return CustomerLedger(customer=to_customer_read(customer, final_balance), transactions=entries)
