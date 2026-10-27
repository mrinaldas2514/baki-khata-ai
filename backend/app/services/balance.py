"""Balance calculation: the single source of truth for "how much does a customer owe".

    balance = total credit - total payment

  * positive -> the customer owes the shop (baki)
  * zero     -> fully settled
  * negative -> the customer has paid in advance

The balance is never stored; it is always worked out from the transactions, so
editing or deleting a transaction automatically corrects it.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from typing import Protocol

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionType


class TransactionLike(Protocol):
    type: TransactionType
    amount: int
    created_at: datetime


def signed_amount(type_: TransactionType, amount: int) -> int:
    """Credit adds to what the customer owes; payment subtracts from it."""
    return amount if type_ == TransactionType.CREDIT else -amount


def calculate_balance(transactions: Iterable[TransactionLike]) -> int:
    return sum(signed_amount(t.type, t.amount) for t in transactions)


def running_balances(transactions: Iterable[TransactionLike]) -> list[int]:
    """Balance after each transaction. Expects transactions in chronological order."""
    balances: list[int] = []
    balance = 0
    for t in transactions:
        balance += signed_amount(t.type, t.amount)
        balances.append(balance)
    return balances


def oldest_unpaid_credit_at(transactions: Sequence[TransactionLike]) -> datetime | None:
    """When the oldest still-unpaid credit was given, or None if nothing is owed.

    Payments are applied to the oldest credits first (first in, first out), like
    a shopkeeper would: if Rahim took 100 last month and 50 this week, then paid
    100, the old debt is cleared and he only owes the 50 from this week.
    """
    paid = sum(t.amount for t in transactions if t.type == TransactionType.PAYMENT)
    credits = sorted(
        (t for t in transactions if t.type == TransactionType.CREDIT), key=lambda t: t.created_at
    )
    for credit in credits:
        if paid >= credit.amount:
            paid -= credit.amount
        else:
            return credit.created_at
    return None


def _signed_amount_sql():
    return case(
        (Transaction.type == TransactionType.CREDIT, Transaction.amount),
        else_=-Transaction.amount,
    )


def balance_sql():
    """SQL expression for the same calculation, so balances can be summed in the database."""
    return func.coalesce(func.sum(_signed_amount_sql()), 0)


def running_balance_sql():
    """SQL version of `running_balances`: the balance after each row, for one customer's rows.

    A window function, so one page of a long ledger can be read without loading the rest.
    """
    return func.sum(_signed_amount_sql()).over(
        partition_by=Transaction.customer_id,
        order_by=(Transaction.created_at, Transaction.id),
    )


def get_customer_balance(db: Session, customer_id: int) -> int:
    stmt = select(balance_sql()).where(Transaction.customer_id == customer_id)
    return int(db.scalar(stmt))


def get_shop_balances(db: Session, shop_id: int) -> dict[int, int]:
    """Balance per customer id, for customers in the shop that have any transactions."""
    stmt = (
        select(Transaction.customer_id, balance_sql())
        .where(Transaction.shop_id == shop_id)
        .group_by(Transaction.customer_id)
    )
    return {customer_id: int(balance) for customer_id, balance in db.execute(stmt)}


def get_owed_since(db: Session, customer_ids: Collection[int]) -> dict[int, datetime]:
    """`oldest_unpaid_credit_at` for each of these customers that still owes something."""
    if not customer_ids:
        return {}
    by_customer: dict[int, list[Transaction]] = defaultdict(list)
    for txn in db.scalars(select(Transaction).where(Transaction.customer_id.in_(customer_ids))):
        by_customer[txn.customer_id].append(txn)
    result = {}
    for customer_id, txns in by_customer.items():
        owed_since = oldest_unpaid_credit_at(txns)
        if owed_since is not None:
            result[customer_id] = owed_since
    return result
