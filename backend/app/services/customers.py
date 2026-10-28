from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction
from app.schemas import CustomerCreate, CustomerListItem, CustomerRead, CustomerUpdate
from app.services.balance import balance_sql, get_customer_balance, get_owed_since
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
    customer = add_customer(db, shop_id, data)
    db.commit()
    db.refresh(customer)
    return customer


def add_customer(db: Session, shop_id: int, data: CustomerCreate) -> Customer:
    """Validate and add a customer to the session without committing."""
    get_shop(db, shop_id)
    _ensure_not_duplicate(db, shop_id, data.name, data.note)
    customer = Customer(shop_id=shop_id, **data.model_dump())
    db.add(customer)
    db.flush()
    return customer


def _ensure_not_duplicate(
    db: Session, shop_id: int, name: str, note: str | None, *, except_id: int | None = None
) -> None:
    """Two customers may share a name only if their notes tell them apart."""
    note_matches = (
        Customer.note.is_(None) if note is None else func.lower(Customer.note) == note.lower()
    )
    stmt = select(Customer.id).where(
        Customer.shop_id == shop_id,
        func.lower(Customer.name) == name.lower(),
        note_matches,
    )
    if except_id is not None:
        stmt = stmt.where(Customer.id != except_id)
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


def update_customer(
    db: Session, shop_id: int, customer_id: int, data: CustomerUpdate
) -> CustomerRead:
    customer = get_customer(db, shop_id, customer_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes or "note" in changes:
        _ensure_not_duplicate(
            db,
            shop_id,
            changes.get("name", customer.name),
            changes.get("note", customer.note),
            except_id=customer.id,
        )
    for field, value in changes.items():
        setattr(customer, field, value)
    db.commit()
    return to_customer_read(customer, get_customer_balance(db, customer.id))


def delete_customer(db: Session, shop_id: int, customer_id: int) -> None:
    """Only a customer without any entries (e.g. one just created by an entry that was undone).

    Someone with a history keeps it: delete their entries one by one first.
    """
    customer = get_customer(db, shop_id, customer_id)
    has_entries = db.scalar(
        select(Transaction.id).where(Transaction.customer_id == customer.id).limit(1)
    )
    if has_entries is not None:
        raise ConflictError(f"Customer {customer_id} still has transactions")
    db.delete(customer)
    db.commit()


def get_customer_with_balance(db: Session, shop_id: int, customer_id: int) -> CustomerRead:
    customer = get_customer(db, shop_id, customer_id)
    return to_customer_read(customer, get_customer_balance(db, customer.id))


def list_customers(db: Session, shop_id: int, search: str | None = None) -> list[CustomerListItem]:
    """All customers of a shop with their balances (and how old their baki is), sorted by name."""
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
    rows = [(customer, int(balance)) for customer, balance in db.execute(stmt)]
    owed_since = get_owed_since(db, [customer.id for customer, balance in rows if balance > 0])
    return [
        CustomerListItem(
            **to_customer_read(customer, balance).model_dump(),
            owed_since=owed_since.get(customer.id),
        )
        for customer, balance in rows
    ]
