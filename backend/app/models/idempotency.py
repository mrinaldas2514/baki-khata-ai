from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime
from app.time_utils import utc_now


class IdempotencyKey(Base):
    """A save the app may send again (its offline queue retries): the answer it got first.

    The app makes a random key per save and sends it in the Idempotency-Key header; a request
    with a key the shop already used gets this stored answer instead of saving twice.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("shop_id", "key", name="uq_idempotency_keys_shop_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    # sha256 of the endpoint and the request body: the same key with other data is refused.
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
