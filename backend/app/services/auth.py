"""Shopkeeper accounts: register (user + shop), log in, log out, settings, delete everything."""

import logging
from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import RevokedToken, Shop, User
from app.schemas.auth import RegisterRequest, UserRead
from app.schemas.shop import ShopRead
from app.security import burn_password_check, hash_password, verify_password
from app.services.exceptions import ConflictError
from app.services.phones import normalize_mobile
from app.time_utils import utc_now

logger = logging.getLogger(__name__)


class WrongPasswordError(Exception):
    """The password didn't match (account deletion asks for it again)."""


def to_user_read(db: Session, user: User) -> UserRead:
    shop = db.get(Shop, user.shop_id)
    return UserRead(
        id=user.id,
        name=user.name,
        phone=user.phone,
        email=user.email,
        shop=ShopRead.model_validate(shop),
        ai_enabled=user.ai_enabled,
        consent_version=user.consent_version,
        consent_at=user.consent_at,
        created_at=user.created_at,
    )


def register(db: Session, data: RegisterRequest) -> User:
    """Create the shop and its owner together. 409 if the phone or email is already used."""
    taken = [
        column == value
        for column, value in ((User.phone, data.phone), (User.email, data.email))
        if value is not None
    ]
    if db.scalar(select(User.id).where(or_(*taken))) is not None:
        raise ConflictError("An account with this phone number or email already exists")

    now = utc_now()
    shop = Shop(name=data.shop_name, owner_name=data.name)
    db.add(shop)
    db.flush()
    user = User(
        shop_id=shop.id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password),
        ai_enabled=True,
        consent_version=data.consent_version,
        consent_at=now,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Someone registered the same phone/email at the same moment.
        db.rollback()
        raise ConflictError("An account with this phone number or email already exists") from exc
    logger.info("Registered user %d with shop %d", user.id, shop.id)
    return user


def find_user_by_login(db: Session, login: str) -> User | None:
    """`login` is an email (has an @) or a phone number in any accepted format."""
    if "@" in login:
        return db.scalar(select(User).where(User.email == login.strip().lower()))
    try:
        phone = normalize_mobile(login)
    except ValueError:
        return None
    return db.scalar(select(User).where(User.phone == phone))


def authenticate(db: Session, login: str, password: str) -> User | None:
    user = find_user_by_login(db, login)
    if user is None:
        burn_password_check(password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def revoke_token(db: Session, jti: str, expires_at: datetime) -> None:
    """Log out: the token stops working now instead of when it expires."""
    now = utc_now()
    # Housekeeping: tokens that expired don't need to be remembered any more.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
    if db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
    db.commit()


def is_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None


def set_ai_enabled(db: Session, user: User, enabled: bool) -> User:
    user.ai_enabled = enabled
    db.commit()
    logger.info("User %d set ai_enabled=%s", user.id, enabled)
    return user


def delete_account(db: Session, user: User, password: str) -> None:
    """Delete the user, the shop and every customer and transaction in it."""
    if not verify_password(user.password_hash, password):
        raise WrongPasswordError("Wrong password")
    user_id, shop_id = user.id, user.shop_id
    # The database cascades the shop's delete to its user, customers and transactions.
    db.execute(delete(Shop).where(Shop.id == shop_id))
    db.commit()
    db.expunge_all()
    logger.info("Deleted user %d and shop %d with all their data", user_id, shop_id)
