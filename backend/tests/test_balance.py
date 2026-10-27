"""Balance = total credit - total payment, always derived from transactions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models import Customer, Shop, Transaction, TransactionType
from app.services.balance import (
    calculate_balance,
    get_customer_balance,
    get_shop_balances,
    oldest_unpaid_credit_at,
    running_balances,
    signed_amount,
)

CREDIT, PAYMENT = TransactionType.CREDIT, TransactionType.PAYMENT
T0 = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class Txn:
    type: TransactionType
    amount: int
    created_at: datetime = T0


def day(n: int) -> datetime:
    return T0 + timedelta(days=n)


# --- pure calculation -------------------------------------------------------


def test_signed_amount():
    assert signed_amount(CREDIT, 100) == 100
    assert signed_amount(PAYMENT, 100) == -100


def test_no_transactions_means_zero_balance():
    assert calculate_balance([]) == 0


def test_credits_add_up():
    assert calculate_balance([Txn(CREDIT, 100), Txn(CREDIT, 250)]) == 350


def test_payments_reduce_balance():
    assert calculate_balance([Txn(CREDIT, 500), Txn(PAYMENT, 200), Txn(CREDIT, 50)]) == 350


def test_full_payment_settles_balance():
    assert calculate_balance([Txn(CREDIT, 300), Txn(PAYMENT, 300)]) == 0


def test_overpayment_gives_negative_balance_as_advance():
    assert calculate_balance([Txn(CREDIT, 100), Txn(PAYMENT, 150)]) == -50


def test_running_balances():
    txns = [Txn(CREDIT, 500), Txn(PAYMENT, 200), Txn(CREDIT, 100), Txn(PAYMENT, 400)]
    assert running_balances(txns) == [500, 300, 400, 0]
    assert running_balances([]) == []


def test_oldest_unpaid_credit_none_when_nothing_owed():
    assert oldest_unpaid_credit_at([]) is None
    assert oldest_unpaid_credit_at([Txn(CREDIT, 100, day(0)), Txn(PAYMENT, 100, day(1))]) is None


def test_oldest_unpaid_credit_with_no_payments_is_first_credit():
    txns = [Txn(CREDIT, 50, day(5)), Txn(CREDIT, 100, day(0))]  # order should not matter
    assert oldest_unpaid_credit_at(txns) == day(0)


def test_payments_clear_oldest_credits_first():
    txns = [Txn(CREDIT, 100, day(0)), Txn(CREDIT, 50, day(10)), Txn(PAYMENT, 100, day(11))]
    assert oldest_unpaid_credit_at(txns) == day(10)


def test_partial_payment_keeps_oldest_credit_unpaid():
    txns = [Txn(CREDIT, 100, day(0)), Txn(CREDIT, 50, day(10)), Txn(PAYMENT, 99, day(11))]
    assert oldest_unpaid_credit_at(txns) == day(0)


def test_advance_payment_covers_later_credit():
    txns = [Txn(PAYMENT, 100, day(0)), Txn(CREDIT, 60, day(1)), Txn(CREDIT, 80, day(2))]
    assert oldest_unpaid_credit_at(txns) == day(2)


# --- database calculation ---------------------------------------------------


def _seed(db):
    shop = Shop(name="Shop", owner_name="Owner")
    other_shop = Shop(name="Other", owner_name="Other")
    db.add_all([shop, other_shop])
    db.flush()
    rahim = Customer(shop_id=shop.id, name="Rahim")
    karim = Customer(shop_id=shop.id, name="Karim")
    nobody = Customer(shop_id=shop.id, name="No Txns")
    outsider = Customer(shop_id=other_shop.id, name="Outsider")
    db.add_all([rahim, karim, nobody, outsider])
    db.flush()

    def txn(c, type_, amount):
        return Transaction(shop_id=c.shop_id, customer_id=c.id, type=type_, amount=amount)

    db.add_all(
        [
            txn(rahim, CREDIT, 500),
            txn(rahim, PAYMENT, 200),
            txn(karim, CREDIT, 100),
            txn(karim, PAYMENT, 300),
            txn(outsider, CREDIT, 999),
        ]
    )
    db.commit()
    return shop, rahim, karim, nobody


def test_get_customer_balance_from_database(db):
    _, rahim, karim, nobody = _seed(db)
    assert get_customer_balance(db, rahim.id) == 300
    assert get_customer_balance(db, karim.id) == -200
    assert get_customer_balance(db, nobody.id) == 0


def test_get_shop_balances_only_includes_that_shop(db):
    shop, rahim, karim, _ = _seed(db)
    assert get_shop_balances(db, shop.id) == {rahim.id: 300, karim.id: -200}


def test_sql_and_python_calculations_agree(db):
    _, rahim, _, _ = _seed(db)
    txns = db.query(Transaction).filter_by(customer_id=rahim.id).all()
    assert calculate_balance(txns) == get_customer_balance(db, rahim.id)


# --- balance stays correct through the API ----------------------------------


def test_balance_follows_edits_and_deletes(client, shop, customer, add_txn):
    url = f"/shops/{shop['id']}/customers/{customer['id']}"
    credit = add_txn(customer["id"], "credit", 500)
    assert credit["customer_balance"] == 500
    payment = add_txn(customer["id"], "payment", 200)
    assert payment["customer_balance"] == 300

    edited = client.patch(f"/shops/{shop['id']}/transactions/{credit['id']}", json={"amount": 800})
    assert edited.json()["customer_balance"] == 600
    assert client.get(url).json()["balance"] == 600

    client.delete(f"/shops/{shop['id']}/transactions/{payment['id']}")
    assert client.get(url).json()["balance"] == 800
