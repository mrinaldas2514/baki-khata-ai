from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction, TransactionType
from app.schemas import CustomerBalanceSummary, Dashboard, OverdueCustomer
from app.services.balance import get_shop_balances, oldest_unpaid_credit_at
from app.services.shops import get_shop
from app.time_utils import local_day_bounds

TOP_CUSTOMERS_LIMIT = 5


def get_dashboard(
    db: Session, shop_id: int, *, now: datetime, local_tz: ZoneInfo, overdue_days: int = 30
) -> Dashboard:
    get_shop(db, shop_id)

    # Only customers who owe money count towards baki; advance payments don't reduce it.
    owing = {cid: bal for cid, bal in get_shop_balances(db, shop_id).items() if bal > 0}
    customers = _load_customers(db, owing)
    top_ids = sorted(owing, key=lambda cid: (-owing[cid], cid))[:TOP_CUSTOMERS_LIMIT]
    today, today_collection = _today_collection(db, shop_id, now, local_tz)

    return Dashboard(
        total_outstanding=sum(owing.values()),
        customers_with_baki=len(owing),
        today=today,
        today_collection=today_collection,
        top_customers=[_summary(customers[cid], owing[cid]) for cid in top_ids],
        overdue_days=overdue_days,
        overdue_customers=_overdue_customers(db, customers, owing, now, overdue_days),
    )


def _load_customers(db: Session, customer_ids) -> dict[int, Customer]:
    if not customer_ids:
        return {}
    stmt = select(Customer).where(Customer.id.in_(customer_ids))
    return {c.id: c for c in db.scalars(stmt)}


def _summary(customer: Customer, balance: int) -> CustomerBalanceSummary:
    return CustomerBalanceSummary(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        note=customer.note,
        balance=balance,
    )


def _today_collection(db: Session, shop_id: int, now: datetime, local_tz: ZoneInfo):
    """Payments received during the shop's local calendar day."""
    today, day_start, day_end = local_day_bounds(now, local_tz)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.shop_id == shop_id,
            Transaction.type == TransactionType.PAYMENT,
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end,
        )
    )
    return today, int(total)


def _overdue_customers(
    db: Session,
    customers: dict[int, Customer],
    owing: dict[int, int],
    now: datetime,
    overdue_days: int,
) -> list[OverdueCustomer]:
    """Customers whose oldest unpaid credit is older than `overdue_days`, oldest first."""
    if not owing:
        return []
    by_customer: dict[int, list[Transaction]] = defaultdict(list)
    for txn in db.scalars(select(Transaction).where(Transaction.customer_id.in_(owing))):
        by_customer[txn.customer_id].append(txn)

    cutoff = now - timedelta(days=overdue_days)
    result = []
    for customer_id, txns in by_customer.items():
        owed_since = oldest_unpaid_credit_at(txns)
        if owed_since is not None and owed_since < cutoff:
            summary = _summary(customers[customer_id], owing[customer_id])
            result.append(
                OverdueCustomer(
                    **summary.model_dump(),
                    owed_since=owed_since,
                    days_outstanding=(now - owed_since).days,
                )
            )
    return sorted(result, key=lambda c: (c.owed_since, c.id))
