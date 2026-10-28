"""FastAPI dependencies for logged-in requests.

Every /shops/{shop_id}/... router depends on `require_shop_owner`: the token must belong to the
shop in the URL. Another shop's id gets the same 404 as a shop that doesn't exist, so nothing
tells a user whether some other shop is there.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import InvalidTokenError, TokenClaims, decode_access_token
from app.services import auth as auth_service
from app.services.exceptions import NotFoundError

_bearer = HTTPBearer(auto_error=False, description="The access_token from /auth/login")


class NotAuthenticatedError(Exception):
    """No token, or one that is invalid, expired or logged out (401)."""


@dataclass
class AuthContext:
    """The logged-in user and their token (logout needs the token's id and expiry)."""

    user: User
    claims: TokenClaims


def get_auth_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    if credentials is None:
        raise NotAuthenticatedError("Not logged in")
    try:
        claims = decode_access_token(credentials.credentials, request.app.state.jwt_secret)
    except InvalidTokenError as exc:
        raise NotAuthenticatedError(
            "Login has expired, please log in again" if str(exc) == "expired" else "Invalid login"
        ) from exc
    if auth_service.is_revoked(db, claims.jti):
        raise NotAuthenticatedError("Logged out, please log in again")
    user = db.get(User, claims.user_id)
    if user is None or user.shop_id != claims.shop_id:
        # The account was deleted.
        raise NotAuthenticatedError("Invalid login")
    return AuthContext(user=user, claims=claims)


def get_current_user(session: Annotated[AuthContext, Depends(get_auth_session)]) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]
AuthSession = Annotated[AuthContext, Depends(get_auth_session)]


def require_shop_owner(shop_id: int, user: CurrentUser) -> None:
    if user.shop_id != shop_id:
        raise NotFoundError(f"Shop {shop_id} not found")
