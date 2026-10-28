"""Application settings, read from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Baki Khata AI"
    environment: str = "development"
    # Switching to PostgreSQL only requires changing this URL (plus installing a driver).
    database_url: str = "sqlite:///./baki_khata.db"
    # The shop's local timezone. Used to decide what "today" means.
    app_timezone: str = "Asia/Dhaka"
    sql_echo: bool = False
    # Browser origins allowed to call the API (the frontend dev server). Comma-separated.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Which parser /parse uses. "groq": the real model (needs GROQ_API_KEY). "fake": simple
    # rules, no AI and no key, for demos. "auto": groq when a key is set, otherwise fake.
    llm_provider: Literal["auto", "groq", "fake"] = "auto"
    # AI parsing (Groq). Without a key the app still runs (see llm_provider).
    groq_api_key: SecretStr | None = None
    # Must support JSON mode. Groq retires models from time to time; the backend logs a clear
    # error at startup if this one is rejected (see app/groq_models.py).
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 20.0
    # Voice input on the server (POST /transcribe) with Groq's Whisper; uses GROQ_API_KEY too.
    groq_stt_model: str = "whisper-large-v3"
    # Limits for one recording. The app records at ~32 kbit/s, so 30 s is about 120 KB.
    stt_max_audio_bytes: int = Field(default=1_000_000, gt=0)
    stt_max_audio_seconds: float = Field(default=30.0, gt=0)
    # Country calling code added to local phone numbers ("01711-000001") for WhatsApp links.
    # Bangladesh: 880, India: 91.
    phone_country_code: str = Field(default="880", pattern=r"^[1-9][0-9]{0,2}$")

    # Signs login tokens. Must be a long random value in production; anyone who knows it can
    # log in as any shopkeeper. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    # Left empty outside production, a random one is made at startup (everyone is logged out
    # whenever the server restarts).
    jwt_secret: SecretStr | None = None
    # How long a login lasts. A week: a shopkeeper shouldn't type the password every morning,
    # and a lost phone's login still ends on its own (or at once with "Logout").
    jwt_expire_minutes: int = Field(default=7 * 24 * 60, gt=0, le=90 * 24 * 60)

    # Requests allowed per client IP (login, register) or per shop (parse, transcribe).
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = Field(default=10, gt=0)
    rate_limit_register_per_hour: int = Field(default=10, gt=0)
    rate_limit_parse_per_minute: int = Field(default=30, gt=0)
    rate_limit_transcribe_per_minute: int = Field(default=15, gt=0)

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _check_jwt_secret(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if len(value) < 32:
                raise ValueError(
                    "JWT_SECRET is too short (at least 32 characters). Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _blank_provider_is_auto(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() or "auto"
        return value

    @field_validator("app_timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
