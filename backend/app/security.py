"""Passwords (argon2id) and login tokens (JWT, HS256).

A token says which user and shop it is for and when it expires:

    {"sub": "7", "shop": 3, "jti": "<random id>", "iat": ..., "exp": ...}

It is signed with JWT_SECRET, so it can't be changed or made up without the secret. Logging out
puts its `jti` on a deny list until it would have expired anyway (see app.services.auth).
"""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import Settings
from app.time_utils import utc_now

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

# argon2id with the library's defaults (RFC 9106's "low memory" profile: 64 MiB, 3 passes).
# Tests swap in a much cheaper hasher (tests/conftest.py).
password_hasher = PasswordHasher()
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Take as long as a real check, so "no such user" can't be told apart by timing."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    verify_password(_dummy_hash, password)


def resolve_jwt_secret(settings: Settings) -> str:
    """JWT_SECRET, or (outside production only) a random one for this run of the server."""
    if settings.jwt_secret is not None:
        return settings.jwt_secret.get_secret_value()
    if settings.is_production:
        raise RuntimeError(
            "JWT_SECRET is not set. Add a long random value to backend/.env: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    logger.warning(
        "JWT_SECRET is not set: using a random one, so every login ends when the server "
        "restarts. Set JWT_SECRET in backend/.env (see .env.example)."
    )
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    shop_id: int
    jti: str
    expires_at: datetime


class InvalidTokenError(Exception):
    """Missing, malformed, wrongly signed or expired token."""


def create_access_token(
    *, user_id: int, shop_id: int, secret: str, expires_minutes: int, now: datetime | None = None
) -> tuple[str, TokenClaims]:
    issued = (now or utc_now()).replace(microsecond=0)
    claims = TokenClaims(
        user_id=user_id,
        shop_id=shop_id,
        jti=str(uuid.uuid4()),
        expires_at=issued + timedelta(minutes=expires_minutes),
    )
    payload = {
        "sub": str(user_id),
        "shop": shop_id,
        "jti": claims.jti,
        "iat": int(issued.timestamp()),
        "exp": int(claims.expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM), claims


def decode_access_token(token: str, secret: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "shop", "jti", "exp"]},
        )
        return TokenClaims(
            user_id=int(payload["sub"]),
            shop_id=int(payload["shop"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("expired") from exc
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidTokenError("invalid") from exc
