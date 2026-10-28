from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime
from app.time_utils import utc_now


class User(Base):
    """A shopkeeper's login. Each user owns exactly one shop (created together at registration)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("phone IS NOT NULL OR email IS NOT NULL", name="ck_users_phone_or_email"),
        UniqueConstraint("phone", name="uq_users_phone"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    # Either or both. Phone is stored normalized (+8801711000001), email lowercased.
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    # argon2id hash; the password itself is never stored.
    password_hash: Mapped[str] = mapped_column(String(255))
    # "AI bondho rakhun" turns this off: nothing is sent to the AI provider any more.
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Which consent text the shopkeeper agreed to at registration, and when.
    consent_version: Mapped[str] = mapped_column(String(20))
    consent_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class RevokedToken(Base):
    """Access tokens that were logged out before they expired. Rows can go once they expire."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
