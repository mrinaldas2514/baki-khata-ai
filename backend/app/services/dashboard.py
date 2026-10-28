from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction, TransactionType
from app.schemas import CustomerBalanceSummary, Dashboard, DaySummary, OverdueCustomer
from app.services import entry_speed
from app.services.balance import get_owed_since, get_shop_balances
from app.services.shops import get_shop
from app.time_utils import local_day_bounds

TOP_CUSTOMERS_LIMIT = 5
CHART_DAYS = 7


def get_dashboard(
    db: Session, shop_id: int, *, now: datetime, local_tz: ZoneInfo, overdue_days: int = 30
) -> Dashboard:
    get_shop(db, shop_id)

    # Only customers who owe money count towards baki; advance payments don't reduce it.
    owing = {cid: bal for cid, bal in get_shop_balances(db, shop_id).items() if bal > 0}
    customers = _load_customers(db, owing)
    top_ids = sorted(owing, key=lambda cid: (-owing[cid], cid))[:TOP_CUSTOMERS_LIMIT]
    last_days = _daily_totals(db, shop_id, now, local_tz)
    today = last_days[-1]

    return Dashboard(
        total_outstanding=sum(owing.values()),
        customers_with_baki=len(owing),
        today=today.date,
        today_collection=today.payment,
        today_new_credit=today.credit,
        top_customers=[_summary(customers[cid], owing[cid]) for cid in top_ids],
        overdue_days=overdue_days,
        overdue_customers=_overdue_customers(db, customers, owing, now, overdue_days),
        last_7_days=last_days,
        entry_speed=entry_speed.recent_speed(db, shop_id),
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


def _daily_totals(db: Session, shop_id: int, now: datetime, local_tz: ZoneInfo) -> list[DaySummary]:
    """New baki and joma for each of the last CHART_DAYS local days, oldest first, ending today.

    Days are the shop's local calendar days (APP_TIMEZONE), the same as "today's collection".
    """
    today, _, day_end = local_day_bounds(now, local_tz)
    first_day = today - timedelta(days=CHART_DAYS - 1)
    start = datetime.combine(first_day, time.min, tzinfo=local_tz)
    totals: dict[date, dict[TransactionType, int]] = {
        first_day + timedelta(days=i): {TransactionType.CREDIT: 0, TransactionType.PAYMENT: 0}
        for i in range(CHART_DAYS)
    }
    stmt = select(Transaction.created_at, Transaction.type, Transaction.amount).where(
        Transaction.shop_id == shop_id,
        Transaction.created_at >= start,
        Transaction.created_at < day_end,
    )
    for created_at, type_, amount in db.execute(stmt):
        totals[created_at.astimezone(local_tz).date()][type_] += amount
    return [
        DaySummary(
            date=day,
            credit=by_type[TransactionType.CREDIT],
            payment=by_type[TransactionType.PAYMENT],
        )
        for day, by_type in totals.items()
    ]


def _overdue_customers(
    db: Session,
    customers: dict[int, Customer],
    owing: dict[int, int],
    now: datetime,
    overdue_days: int,
) -> list[OverdueCustomer]:
    """Customers whose oldest unpaid credit is older than `overdue_days`, oldest first."""
    cutoff = now - timedelta(days=overdue_days)
    result = []
    for customer_id, owed_since in get_owed_since(db, owing).items():
        if owed_since < cutoff:
            summary = _summary(customers[customer_id], owing[customer_id])
            result.append(
                OverdueCustomer(
                    **summary.model_dump(),
                    owed_since=owed_since,
                    days_outstanding=(now - owed_since).days,
                )
            )
    return sorted(result, key=lambda c: (c.owed_since, c.id))
