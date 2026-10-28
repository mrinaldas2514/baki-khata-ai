"""The whole khata as one CSV file: every customer, and every transaction with its balance.

UTF-8 with a byte order mark, so Excel shows Bangla names and sentences correctly. One row per
transaction (oldest first within each customer), plus one row for each customer who has none.
"""

import csv
import io
import re
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import Customer, Transaction, TransactionType
from app.services.balance import running_balance_sql

BOM = "\ufeff"
HEADER = [
    "customer_id",
    "customer_name",
    "phone",
    "area_note",
    "date",
    "type",
    "amount",
    "item",
    "original_sentence",
    "balance_after",
]
TYPE_LABELS = {TransactionType.CREDIT: "Baki", TransactionType.PAYMENT: "Joma"}

# Excel runs a cell that starts with one of these as a formula ("=HYPERLINK(...)").
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_PHONE = re.compile(r"^\+\d+$")


def _cell(value: str | None) -> str:
    if value is None:
        return ""
    if value.startswith(_FORMULA_START) and not _PHONE.match(value):
        return "'" + value
    return value


def khata_csv(db: Session, shop_id: int, local_tz: ZoneInfo) -> str:
    with_running = (
        select(Transaction, running_balance_sql().label("running_balance"))
        .where(Transaction.shop_id == shop_id)
        .subquery()
    )
    txn = aliased(Transaction, with_running)
    rows = db.execute(
        select(Customer, txn, with_running.c.running_balance)
        .outerjoin(txn, txn.customer_id == Customer.id)
        .where(Customer.shop_id == shop_id)
        .order_by(Customer.name, Customer.id, txn.created_at, txn.id)
    )

    out = io.StringIO()
    out.write(BOM)
    writer = csv.writer(out)
    writer.writerow(HEADER)
    for customer, t, balance in rows:
        base = [customer.id, _cell(customer.name), _cell(customer.phone), _cell(customer.note)]
        if t is None:
            writer.writerow([*base, "", "", "", "", "", ""])
            continue
        writer.writerow(
            [
                *base,
                t.created_at.astimezone(local_tz).strftime("%Y-%m-%d %H:%M"),
                TYPE_LABELS[t.type],
                t.amount,
                _cell(t.item),
                _cell(t.raw_text),
                balance,
            ]
        )
    return out.getvalue()
