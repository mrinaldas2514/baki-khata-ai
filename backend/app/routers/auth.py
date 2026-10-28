from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import AuthSession, CurrentUser, NotAuthenticatedError
from app.database import get_db
from app.models import User
from app.rate_limit import check_rate, client_ip
from app.schemas.auth import (
    AuthResult,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    SettingsUpdate,
    UserRead,
)
from app.security import create_access_token
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["accounts"])
DB = Annotated[Session, Depends(get_db)]


def _login_result(request: Request, db: Session, user: User) -> AuthResult:
    token, claims = create_access_token(
        user_id=user.id,
        shop_id=user.shop_id,
        secret=request.app.state.jwt_secret,
        expires_minutes=request.app.state.jwt_expire_minutes,
    )
    return AuthResult(
        access_token=token, expires_at=claims.expires_at, user=service.to_user_read(db, user)
    )


@router.post("/register", response_model=AuthResult, status_code=status.HTTP_201_CREATED)
def register(request: Request, data: RegisterRequest, db: DB):
    """Create a shop and its shopkeeper's login, and log in. `consent` must be true."""
    check_rate(request, "register", client_ip(request))
    return _login_result(request, db, service.register(db, data))


@router.post("/login", response_model=AuthResult)
def login(request: Request, data: LoginRequest, db: DB):
    """Log in with a phone number (any format) or email. 401 if either is wrong."""
    check_rate(request, "login", client_ip(request))
    # Also per account, so guessing one shop's password from many addresses is slow too.
    check_rate(request, "login", f"account:{data.login.lower()}")
    user = service.authenticate(db, data.login, data.password)
    if user is None:
        raise NotAuthenticatedError("Wrong phone/email or password")
    return _login_result(request, db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(session: AuthSession, db: DB):
    """This token stops working at once."""
    service.revoke_token(db, session.claims.jti, session.claims.expires_at)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser, db: DB):
    return service.to_user_read(db, user)


@router.patch("/me", response_model=UserRead)
def update_settings(data: SettingsUpdate, user: CurrentUser, db: DB):
    """Settings. `ai_enabled: false` ("AI bondho rakhun"): nothing goes to the AI provider."""
    return service.to_user_read(db, service.set_ai_enabled(db, user, data.ai_enabled))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(data: DeleteAccountRequest, session: AuthSession, db: DB):
    """Delete the account, the shop and all its customers and transactions. Needs the password."""
    claims = session.claims
    service.delete_account(db, session.user, data.password)
    service.revoke_token(db, claims.jti, claims.expires_at)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
