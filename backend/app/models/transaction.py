import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime
from app.time_utils import utc_now


class TransactionType(enum.StrEnum):
    CREDIT = "credit"  # customer took goods on baki (balance goes up)
    PAYMENT = "payment"  # customer paid money (balance goes down)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        Index("ix_transactions_customer_created", "customer_id", "created_at"),
        Index("ix_transactions_shop_created", "shop_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda members: [m.value for m in members],
        )
    )
    # Whole taka, always positive. The `type` decides the direction.
    amount: Mapped[int] = mapped_column(Integer)
    item: Mapped[str | None] = mapped_column(String(200))
    # The original sentence the shopkeeper typed or spoke, kept for later review.
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
