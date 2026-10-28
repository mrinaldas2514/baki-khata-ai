from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Customer, Shop, Transaction, TransactionType
from app.services.dashboard import get_dashboard


def ago(**delta) -> str:
    return (datetime.now(UTC) - timedelta(**delta)).isoformat()


def dashboard(client, shop, **params):
    response = client.get(f"/shops/{shop['id']}/dashboard", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_dashboard(client, shop):
    body = dashboard(client, shop)
    assert body["total_outstanding"] == 0
    assert body["customers_with_baki"] == 0
    assert body["today_collection"] == 0
    assert body["top_customers"] == []
    assert body["overdue_customers"] == []
    assert body["overdue_days"] == 30
    assert body["today"] == datetime.now(ZoneInfo("Asia/Dhaka")).date().isoformat()


def test_total_outstanding_ignores_settled_and_advance_customers(
    client, shop, make_customer, add_txn
):
    owes = make_customer("Owes")
    settled = make_customer("Settled")
    advance = make_customer("Advance")
    add_txn(owes["id"], "credit", 500)
    add_txn(owes["id"], "payment", 100)
    add_txn(settled["id"], "credit", 200)
    add_txn(settled["id"], "payment", 200)
    add_txn(advance["id"], "payment", 300)

    body = dashboard(client, shop)
    assert body["total_outstanding"] == 400
    assert body["customers_with_baki"] == 1


def test_today_collection_counts_only_todays_payments(client, shop, make_customer, add_txn):
    c = make_customer("Rahim")
    add_txn(c["id"], "credit", 1000, created_at=ago(days=3))
    add_txn(c["id"], "payment", 100)
    add_txn(c["id"], "payment", 50)
    add_txn(c["id"], "payment", 400, created_at=ago(days=2))  # not today
    add_txn(c["id"], "credit", 70)  # credit, not a collection

    assert dashboard(client, shop)["today_collection"] == 150


def test_top_five_customers_by_balance(client, shop, make_customer, add_txn):
    for i, amount in enumerate([100, 600, 300, 50, 900, 400, 200]):
        c = make_customer(f"Customer {i}")
        add_txn(c["id"], "credit", amount)
    zero = make_customer("Zero")
    add_txn(zero["id"], "credit", 5000)
    add_txn(zero["id"], "payment", 5000)

    top = dashboard(client, shop)["top_customers"]
    assert [c["balance"] for c in top] == [900, 600, 400, 300, 200]
    assert top[0]["name"] == "Customer 4"
    assert set(top[0]) == {"id", "name", "phone", "note", "balance"}


def test_overdue_customers(client, shop, make_customer, add_txn):
    old = make_customer("Old debt", phone="01700000000")
    add_txn(old["id"], "credit", 300, created_at=ago(days=45))
    add_txn(old["id"], "payment", 100, created_at=ago(days=10))

    older = make_customer("Older debt")
    add_txn(older["id"], "credit", 50, created_at=ago(days=60))

    recent = make_customer("Recent")
    add_txn(recent["id"], "credit", 999, created_at=ago(days=29))

    # Old credit fully covered by a payment: only the recent credit is unpaid.
    cleared = make_customer("Cleared old")
    add_txn(cleared["id"], "credit", 100, created_at=ago(days=40))
    add_txn(cleared["id"], "credit", 80, created_at=ago(days=5))
    add_txn(cleared["id"], "payment", 100)

    settled = make_customer("Settled")
    add_txn(settled["id"], "credit", 100, created_at=ago(days=90))
    add_txn(settled["id"], "payment", 100, created_at=ago(days=80))

    overdue = dashboard(client, shop)["overdue_customers"]
    assert [(c["name"], c["balance"], c["days_outstanding"]) for c in overdue] == [
        ("Older debt", 50, 60),
        ("Old debt", 200, 45),
    ]
    assert overdue[1]["phone"] == "+8801700000000"  # stored normalized
    assert overdue[1]["owed_since"]


def test_overdue_days_can_be_changed(client, shop, make_customer, add_txn):
    c = make_customer("Rahim")
    add_txn(c["id"], "credit", 100, created_at=ago(days=10))
    assert dashboard(client, shop)["overdue_customers"] == []
    body = dashboard(client, shop, overdue_days=7)
    assert body["overdue_days"] == 7
    assert [o["name"] for o in body["overdue_customers"]] == ["Rahim"]


def test_overdue_days_validation(client, shop):
    response = client.get(f"/shops/{shop['id']}/dashboard", params={"overdue_days": 0})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "overdue_days"


def test_dashboard_ignores_other_shops(client, shop, make_customer, add_txn, other_shop):
    other = other_shop
    as_other = {"headers": other["headers"]}
    c = client.post(f"/shops/{other['id']}/customers", json={"name": "Outsider"}, **as_other).json()
    client.post(
        f"/shops/{other['id']}/customers/{c['id']}/transactions",
        json={"type": "credit", "amount": 500, "created_at": ago(days=50)},
        **as_other,
    )
    client.post(
        f"/shops/{other['id']}/customers/{c['id']}/transactions",
        json={"type": "payment", "amount": 100},
        **as_other,
    )
    body = dashboard(client, shop)
    assert body["total_outstanding"] == 0
    assert body["today_collection"] == 0
    assert body["overdue_customers"] == []


def test_dashboard_for_missing_shop(client):
    assert client.get("/shops/999/dashboard").status_code == 404


def test_today_uses_shop_local_day(db):
    """At 01:00 in Dhaka (19:00 UTC the day before), 'today' starts at 18:00 UTC."""
    shop = Shop(name="S", owner_name="O")
    db.add(shop)
    db.flush()
    c = Customer(shop_id=shop.id, name="Rahim")
    db.add(c)
    db.flush()

    def pay(amount, at):
        db.add(
            Transaction(
                shop_id=shop.id,
                customer_id=c.id,
                type=TransactionType.PAYMENT,
                amount=amount,
                created_at=at,
            )
        )

    pay(10, datetime(2026, 10, 25, 17, 30, tzinfo=UTC))  # 23:30 on the 25th in Dhaka
    pay(20, datetime(2026, 10, 25, 18, 30, tzinfo=UTC))  # 00:30 on the 26th in Dhaka
    db.commit()

    now = datetime(2026, 10, 25, 19, 0, tzinfo=UTC)
    dhaka = get_dashboard(db, shop.id, now=now, local_tz=ZoneInfo("Asia/Dhaka"))
    assert dhaka.today.isoformat() == "2026-10-26"
    assert dhaka.today_collection == 20

    utc = get_dashboard(db, shop.id, now=now, local_tz=ZoneInfo("UTC"))
    assert utc.today.isoformat() == "2026-10-25"
    assert utc.today_collection == 30


def test_today_new_credit_and_last_7_days(client, shop, make_customer, add_txn):
    c = make_customer("Rahim")
    add_txn(c["id"], "credit", 900, created_at=ago(days=10))  # before the chart
    add_txn(c["id"], "credit", 300, created_at=ago(days=6))
    add_txn(c["id"], "payment", 100, created_at=ago(days=6))
    add_txn(c["id"], "credit", 40, created_at=ago(days=2))
    add_txn(c["id"], "credit", 120)
    add_txn(c["id"], "credit", 80)
    add_txn(c["id"], "payment", 60)

    body = dashboard(client, shop)
    assert body["today_new_credit"] == 200
    assert body["today_collection"] == 60
    days = body["last_7_days"]
    assert len(days) == 7
    assert days[-1] == {"date": body["today"], "credit": 200, "payment": 60}
    assert [(d["credit"], d["payment"]) for d in days] == [
        (300, 100), (0, 0), (0, 0), (0, 0), (40, 0), (0, 0), (200, 60),
    ]  # fmt: skip
    dates = [datetime.fromisoformat(d["date"]).date() for d in days]
    assert all((b - a).days == 1 for a, b in zip(dates, dates[1:], strict=False))


def test_last_7_days_uses_shop_local_days(db):
    shop = Shop(name="S", owner_name="O")
    db.add(shop)
    db.flush()
    c = Customer(shop_id=shop.id, name="Rahim")
    db.add(c)
    db.flush()
    # 23:30 on the 25th and 00:30 on the 26th in Dhaka (UTC+6).
    for amount, at in [
        (10, datetime(2026, 10, 25, 17, 30, tzinfo=UTC)),
        (20, datetime(2026, 10, 25, 18, 30, tzinfo=UTC)),
    ]:
        db.add(
            Transaction(
                shop_id=shop.id,
                customer_id=c.id,
                type=TransactionType.CREDIT,
                amount=amount,
                created_at=at,
            )
        )
    db.commit()

    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    days = get_dashboard(db, shop.id, now=now, local_tz=ZoneInfo("Asia/Dhaka")).last_7_days
    assert [(d.date.isoformat(), d.credit) for d in days[-2:]] == [
        ("2026-10-25", 10),
        ("2026-10-26", 20),
    ]
    assert days[0].date.isoformat() == "2026-10-20"
    assert (
        get_dashboard(db, shop.id, now=now, local_tz=ZoneInfo("Asia/Dhaka")).today_new_credit == 20
    )
