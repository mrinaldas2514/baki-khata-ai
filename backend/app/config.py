"""Application settings, read from environment variables (and an optional .env file)."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Baki Khata AI"
    environment: str = "development"
    # Switching to PostgreSQL only requires changing this URL (plus installing a driver).
    database_url: str = "sqlite:///./baki_khata.db"
    # The shop's local timezone. Used to decide what "today" means.
    app_timezone: str = "Asia/Dhaka"
    sql_echo: bool = False

    # AI parsing (Groq). Without a key the app still runs; only /parse returns 503.
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 20.0

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
