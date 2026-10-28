from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.privacy import CONSENT_VERSION
from app.schemas.common import Email, Name, Phone
from app.schemas.shop import ShopRead

Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    name: Name = Field(description="The shopkeeper's name (used to sign reminders)")
    shop_name: Name
    phone: Phone = Field(default=None, description="Bangladesh or India mobile; used to log in")
    email: Email = Field(default=None, description="Optional, can be used to log in instead")
    password: Password
    consent: bool = Field(description="Must be true: the shopkeeper agreed to the privacy note")
    consent_version: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] = (
        Field(description="Which version of the privacy note was shown")
    )

    @field_validator("consent")
    @classmethod
    def _consent_given(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Please read the privacy note and tick the box to continue")
        return value

    @field_validator("consent_version")
    @classmethod
    def _current_version(cls, value: str) -> str:
        if value != CONSENT_VERSION:
            raise ValueError("The privacy note has changed. Reload the page and read it again")
        return value

    @model_validator(mode="after")
    def _phone_or_email(self) -> "RegisterRequest":
        if self.phone is None and self.email is None:
            raise ValueError("Give a phone number or an email to log in with")
        return self


class LoginRequest(BaseModel):
    login: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)
    ] = Field(description="Phone number or email", examples=["01711000001"])
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    email: str | None
    shop: ShopRead
    ai_enabled: bool = Field(description="False: nothing is sent to the AI provider")
    consent_version: str
    consent_at: datetime
    created_at: datetime


class AuthResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class SettingsUpdate(BaseModel):
    ai_enabled: bool = Field(
        description="false = 'AI bondho rakhun': only the rule-based parser and the manual form"
    )


class DeleteAccountRequest(BaseModel):
    password: Annotated[str, Field(min_length=1, max_length=128)] = Field(
        description="The account's password, to confirm"
    )
