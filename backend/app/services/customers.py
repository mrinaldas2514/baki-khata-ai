from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction
from app.schemas import CustomerCreate, CustomerRead
from app.services.balance import balance_sql, get_customer_balance
from app.services.exceptions import ConflictError, NotFoundError
from app.services.shops import get_shop


def to_customer_read(customer: Customer, balance: int) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        shop_id=customer.shop_id,
        name=customer.name,
        phone=customer.phone,
        note=customer.note,
        created_at=customer.created_at,
        balance=balance,
    )


def create_customer(db: Session, shop_id: int, data: CustomerCreate) -> Customer:
    get_shop(db, shop_id)
    _ensure_not_duplicate(db, shop_id, data.name, data.note)
    customer = Customer(shop_id=shop_id, **data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _ensure_not_duplicate(db: Session, shop_id: int, name: str, note: str | None) -> None:
    """Two customers may share a name only if their notes tell them apart."""
    note_matches = (
        Customer.note.is_(None) if note is None else func.lower(Customer.note) == note.lower()
    )
    stmt = select(Customer.id).where(
        Customer.shop_id == shop_id,
        func.lower(Customer.name) == name.lower(),
        note_matches,
    )
    if db.scalar(stmt) is not None:
        hint = f" with note '{note}'" if note else " without a note"
        raise ConflictError(
            f"A customer named '{name}'{hint} already exists in this shop. "
            "Add a different area/note to tell them apart."
        )


def get_customer(db: Session, shop_id: int, customer_id: int) -> Customer:
    get_shop(db, shop_id)
    customer = db.get(Customer, customer_id)
    if customer is None or customer.shop_id != shop_id:
        raise NotFoundError(f"Customer {customer_id} not found in shop {shop_id}")
    return customer


def get_customer_with_balance(db: Session, shop_id: int, customer_id: int) -> CustomerRead:
    customer = get_customer(db, shop_id, customer_id)
    return to_customer_read(customer, get_customer_balance(db, customer.id))


def list_customers(db: Session, shop_id: int, search: str | None = None) -> list[CustomerRead]:
    """All customers of a shop with their balances, sorted by name."""
    get_shop(db, shop_id)
    stmt = (
        select(Customer, balance_sql())
        .outerjoin(Transaction, Transaction.customer_id == Customer.id)
        .where(Customer.shop_id == shop_id)
        .group_by(Customer.id)
        .order_by(func.lower(Customer.name), Customer.id)
    )
    if search and search.strip():
        term = search.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(Customer.name).contains(term, autoescape=True),
                func.lower(Customer.note).contains(term, autoescape=True),
                Customer.phone.contains(term, autoescape=True),
            )
        )
    return [to_customer_read(customer, int(balance)) for customer, balance in db.execute(stmt)]
