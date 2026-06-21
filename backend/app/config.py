from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    """Runtime configuration.

    Secret values may be loaded from the environment or .env files, but they
    must never be serialized into status responses.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    version: str = Field(default=__version__, validation_alias="APP_VERSION")
    afferens_base_url: AnyHttpUrl = Field(
        default="https://afferens.com",
        validation_alias="AFFERENS_BASE_URL",
    )
    afferens_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="AFFERENS_API_KEY",
    )
    afferens_timeout_seconds: float = Field(
        default=10.0,
        ge=0.1,
        le=60.0,
        validation_alias="AFFERENS_TIMEOUT_SECONDS",
    )
    database_url: SecretStr | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    database_enabled: bool = Field(
        default=True,
        validation_alias="DATABASE_ENABLED",
    )
    database_connect_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=30,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )
    fireworks_base_url: AnyHttpUrl = Field(
        default="https://api.fireworks.ai/inference/v1",
        validation_alias="FIREWORKS_BASE_URL",
    )
    fireworks_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="FIREWORKS_API_KEY",
    )
    fireworks_model: str = Field(
        default="accounts/fireworks/models/deepseek-v3p1",
        validation_alias="FIREWORKS_MODEL",
    )
    fireworks_timeout_seconds: float = Field(
        default=20.0,
        ge=0.1,
        le=120.0,
        validation_alias="FIREWORKS_TIMEOUT_SECONDS",
    )

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower() or "development"

    @property
    def afferens_configured(self) -> bool:
        key = self.afferens_api_key
        return bool(key and key.get_secret_value().strip())

    def afferens_key_value(self) -> str | None:
        if not self.afferens_configured or self.afferens_api_key is None:
            return None
        return self.afferens_api_key.get_secret_value().strip()

    @property
    def database_configured(self) -> bool:
        url = self.database_url
        return bool(url and url.get_secret_value().strip())

    @property
    def database_available_for_runtime(self) -> bool:
        return self.database_enabled and self.database_configured

    def database_url_value(self) -> str | None:
        if not self.database_configured or self.database_url is None:
            return None
        return self.database_url.get_secret_value().strip()

    @property
    def fireworks_configured(self) -> bool:
        key = self.fireworks_api_key
        return bool(key and key.get_secret_value().strip())

    def fireworks_key_value(self) -> str | None:
        if not self.fireworks_configured or self.fireworks_api_key is None:
            return None
        return self.fireworks_api_key.get_secret_value().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
