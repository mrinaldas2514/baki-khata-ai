import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime
from app.time_utils import utc_now


class InputMethod(enum.StrEnum):
    TYPED = "typed"
    VOICE = "voice"


class EntryTiming(Base):
    """How long one entry took, from the first keystroke or mic press until it was saved.

    Only numbers: no text, no customer, nothing that says what was written.
    """

    __tablename__ = "entry_timings"
    __table_args__ = (Index("ix_entry_timings_shop_created", "shop_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    duration_ms: Mapped[int] = mapped_column(Integer)
    input_method: Mapped[InputMethod] = mapped_column(
        Enum(
            InputMethod,
            name="input_method",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda members: [m.value for m in members],
        )
    )
    # How many entries were saved together (a sentence about several customers).
    entry_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
