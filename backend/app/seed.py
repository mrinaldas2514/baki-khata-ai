"""Create a demo shop with customers and transactions, so the app has something to show.

    cd backend
    python -m app.seed            # creates "Demo Dokan" if it doesn't exist yet
    python -m app.seed --reset    # deletes the demo shop and creates it again

Prints the shop id; put it in frontend/.env as VITE_SHOP_ID (it's 1 on a fresh database).
"""

import argparse
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import build_engine, create_tables
from app.models import Shop, TransactionType
from app.schemas import CustomerCreate, ShopCreate, TransactionCreate
from app.services import customers as customer_service
from app.services import transactions as transaction_service
from app.time_utils import utc_now

DEMO_SHOP = ShopCreate(name="Demo Dokan", owner_name="Karim")

# (name, note, phone). The two Rahims show how the app asks "which Rahim?".
CUSTOMERS = [
    ("Rahim", "Bazar road", "01711-000001"),
    ("Rahim", "Tea stall", None),
    ("Salma", None, "01811-000002"),
    ("Jasim", None, None),
    ("Shopon", "School gate", None),
    ("Nasima", None, "01911-000003"),
    ("Abul", None, None),
    ("আয়েশা", None, None),
]

CREDIT, PAYMENT = TransactionType.CREDIT, TransactionType.PAYMENT

# (customer index, days ago, type, amount, item, raw_text). Oldest first.
TRANSACTIONS = [
    (0, 40, CREDIT, 300, "chal", "rahim bhai 300 taka chal baki"),
    (3, 35, CREDIT, 1500, "gas cylinder", "jasim kaka dedh hajar baki, gas cylinder"),
    (2, 20, CREDIT, 500, "dal, tel", "salma apa pach sho taka baki, dal r tel"),
    (4, 15, CREDIT, 850, "5 liter tel", "Shopon 5 liter tel 850 tk baki"),
    (0, 12, PAYMENT, 200, None, "rahim 200 dilo"),
    (5, 10, CREDIT, 1200, "chal, dal", "nasima apa 1200 taka chal r dal baki"),
    (1, 7, CREDIT, 60, "cha, biscuit", "rahim tea stall 60 taka cha biscuit baki"),
    (6, 6, CREDIT, 2500, "chini", "Abul 2,500 tk chini baki"),
    (7, 5, CREDIT, 750, "চাল", "আয়েশা আপা ৭৫০ টাকার চাল নিলো"),
    (2, 3, PAYMENT, 300, None, "salma 300 joma dilo"),
    (4, 2, CREDIT, 120, "2 kg alu", "shopon 2 kg alu 120 taka baki"),
    (5, 1, PAYMENT, 1000, None, "nasima 1000 dilen"),
    (6, 0, PAYMENT, 500, None, "Abul 500 taka dilo"),
]


def seed(db: Session, reset: bool = False) -> Shop:
    existing = db.scalar(select(Shop).where(Shop.name == DEMO_SHOP.name).order_by(Shop.id))
    if existing is not None and not reset:
        return existing
    if existing is not None:
        db.delete(existing)  # customers and transactions go with it (ON DELETE CASCADE)
        db.commit()

    shop = Shop(**DEMO_SHOP.model_dump())
    db.add(shop)
    db.flush()
    customers = [
        customer_service.add_customer(db, shop.id, CustomerCreate(name=n, note=note, phone=phone))
        for n, note, phone in CUSTOMERS
    ]
    now = utc_now()
    for index, days_ago, type_, amount, item, raw_text in TRANSACTIONS:
        transaction_service.add_transaction(
            db,
            customers[index],
            TransactionCreate(
                type=type_,
                amount=amount,
                item=item,
                raw_text=raw_text,
                created_at=now - timedelta(days=days_ago, minutes=30),
            ),
        )
    db.commit()
    return shop


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete and recreate the demo shop")
    args = parser.parse_args()

    settings = get_settings()
    engine = build_engine(settings.database_url)
    create_tables(engine)
    with Session(engine, expire_on_commit=False) as db:
        before = db.scalar(select(Shop.id).where(Shop.name == DEMO_SHOP.name))
        shop = seed(db, reset=args.reset)
    if before is not None and not args.reset:
        print(f"Demo shop already exists (id {shop.id}). Use --reset to recreate it.")
    else:
        print(f"Created demo shop '{shop.name}' with id {shop.id}.")
    print(f"Set VITE_SHOP_ID={shop.id} in frontend/.env")


if __name__ == "__main__":
    main()
