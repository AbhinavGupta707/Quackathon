from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class ConfigIssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ConfigValidationIssue(BaseModel):
    severity: ConfigIssueSeverity
    code: str
    message: str
    required: bool = False


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
    startup_validation_strict: bool | None = Field(
        default=None,
        validation_alias="STARTUP_VALIDATION_STRICT",
    )
    fixture_mode: bool = Field(default=False, validation_alias="FIXTURE_MODE")
    public_api_base_url: AnyHttpUrl | None = Field(
        default=None,
        validation_alias="PUBLIC_API_BASE_URL",
    )
    frontend_public_url: AnyHttpUrl | None = Field(
        default=None,
        validation_alias="FRONTEND_PUBLIC_URL",
    )
    cors_allowed_origins: str = Field(
        default="",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
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
    afferens_actuation_enabled: bool = Field(
        default=False,
        validation_alias="AFFERENS_ACTUATION_ENABLED",
    )
    afferens_actuation_supported_commands: str = Field(
        default="TRIGGER_ALARM,CAPTURE_FRAME",
        validation_alias="AFFERENS_ACTUATION_SUPPORTED_COMMANDS",
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
    object_recent_window_seconds: int = Field(
        default=300,
        ge=1,
        le=86400,
        validation_alias="OBJECT_RECENT_WINDOW_SECONDS",
    )
    ambient_default_poll_interval_seconds: int = Field(
        default=45,
        ge=3,
        le=3600,
        validation_alias="AMBIENT_DEFAULT_POLL_INTERVAL_SECONDS",
    )
    action_yolo_fall_enabled: bool = Field(
        default=False,
        validation_alias="ACTION_YOLO_FALL_ENABLED",
    )
    action_yolo_fall_model_path: str | None = Field(
        default=None,
        validation_alias="ACTION_YOLO_FALL_MODEL_PATH",
    )
    action_yolo_fall_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        validation_alias="ACTION_YOLO_FALL_CONFIDENCE_THRESHOLD",
    )
    action_yolo_fall_fallen_labels: str = Field(
        default=(
            "fall,fallen,fallen_person,lying,lying_down,lying_on_floor,"
            "horizontal_posture,floor_posture"
        ),
        validation_alias="ACTION_YOLO_FALL_FALLEN_LABELS",
    )
    action_yolo_fall_non_fallen_labels: str = Field(
        default="not_fallen,standing,person,upright,sitting",
        validation_alias="ACTION_YOLO_FALL_NON_FALLEN_LABELS",
    )
    action_fall_persistence_seconds: float = Field(
        default=3.5,
        ge=0.5,
        le=60.0,
        validation_alias="ACTION_FALL_PERSISTENCE_SECONDS",
    )
    action_fall_debounce_seconds: int = Field(
        default=120,
        ge=1,
        le=3600,
        validation_alias="ACTION_FALL_DEBOUNCE_SECONDS",
    )
    action_drink_min_window_seconds: float = Field(
        default=1.0,
        ge=0.0,
        le=60.0,
        validation_alias="ACTION_DRINK_MIN_WINDOW_SECONDS",
    )
    action_raw_video_storage_enabled: bool = Field(
        default=False,
        validation_alias="ACTION_RAW_VIDEO_STORAGE_ENABLED",
    )
    action_max_frame_bytes: int = Field(
        default=4_000_000,
        ge=1,
        le=25_000_000,
        validation_alias="ACTION_MAX_FRAME_BYTES",
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
        default="accounts/fireworks/models/deepseek-v4-flash",
        validation_alias="FIREWORKS_MODEL",
    )
    fireworks_timeout_seconds: float = Field(
        default=20.0,
        ge=0.1,
        le=120.0,
        validation_alias="FIREWORKS_TIMEOUT_SECONDS",
    )
    langsmith_tracing: bool = Field(
        default=False,
        validation_alias="LANGSMITH_TRACING",
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LANGSMITH_API_KEY",
    )
    langsmith_project: str = Field(
        default="afferens-memory-guardian-local",
        validation_alias="LANGSMITH_PROJECT",
    )
    langsmith_endpoint: AnyHttpUrl = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGSMITH_ENDPOINT",
    )
    langsmith_trace_content: bool = Field(
        default=False,
        validation_alias="LANGSMITH_TRACE_CONTENT",
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        validation_alias="GEMINI_MODEL",
    )
    parcle_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="PARCLE_API_KEY",
    )
    parcel_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="PARCEL_API_KEY",
    )
    semantic_memory_enabled: bool = Field(
        default=False,
        validation_alias="SEMANTIC_MEMORY_ENABLED",
    )
    embedding_provider: str = Field(
        default="none",
        validation_alias="EMBEDDING_PROVIDER",
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias="EMBEDDING_MODEL",
    )

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower() or "development"

    @property
    def is_production_profile(self) -> bool:
        return self.environment in {"production", "prod", "staging"}

    @property
    def strict_startup_validation(self) -> bool:
        if self.startup_validation_strict is not None:
            return self.startup_validation_strict
        return self.is_production_profile

    @property
    def public_api_base_url_value(self) -> str | None:
        return str(self.public_api_base_url).rstrip("/") if self.public_api_base_url else None

    @property
    def frontend_public_url_value(self) -> str | None:
        return str(self.frontend_public_url).rstrip("/") if self.frontend_public_url else None

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        configured = _parse_csv(self.cors_allowed_origins)
        origins = configured or ([] if self.is_production_profile else _local_cors_origins())
        frontend_url = self.frontend_public_url_value
        if frontend_url and frontend_url not in origins:
            origins.append(frontend_url)
        return origins

    @property
    def afferens_configured(self) -> bool:
        key = self.afferens_api_key
        return bool(key and key.get_secret_value().strip())

    def afferens_key_value(self) -> str | None:
        if not self.afferens_configured or self.afferens_api_key is None:
            return None
        return self.afferens_api_key.get_secret_value().strip()

    @property
    def afferens_supported_actuation_commands(self) -> set[str]:
        return {
            item.strip().upper()
            for item in self.afferens_actuation_supported_commands.split(",")
            if item.strip()
        }

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

    @property
    def langsmith_configured(self) -> bool:
        key = self.langsmith_api_key
        return bool(key and key.get_secret_value().strip())

    @property
    def langsmith_runtime_enabled(self) -> bool:
        return self.langsmith_tracing and self.langsmith_configured

    def langsmith_key_value(self) -> str | None:
        if not self.langsmith_configured or self.langsmith_api_key is None:
            return None
        return self.langsmith_api_key.get_secret_value().strip()

    @property
    def gemini_configured(self) -> bool:
        key = self.gemini_api_key
        return bool(key and key.get_secret_value().strip())

    def gemini_key_value(self) -> str | None:
        if not self.gemini_configured or self.gemini_api_key is None:
            return None
        return self.gemini_api_key.get_secret_value().strip()

    @property
    def parcle_configured(self) -> bool:
        key = self.parcle_api_key
        return bool(key and key.get_secret_value().strip())

    @property
    def parcel_configured(self) -> bool:
        key = self.parcel_api_key
        return bool(key and key.get_secret_value().strip())

    @property
    def embedding_provider_normalized(self) -> str:
        return (self.embedding_provider or "none").strip().lower() or "none"

    @property
    def embedding_configured(self) -> bool:
        return self.embedding_provider_normalized not in {"", "none", "disabled"}

    @property
    def action_yolo_fall_fallen_label_set(self) -> set[str]:
        return _normalize_label_list(self.action_yolo_fall_fallen_labels)

    @property
    def action_yolo_fall_non_fallen_label_set(self) -> set[str]:
        return _normalize_label_list(self.action_yolo_fall_non_fallen_labels)

    def validate_startup_environment(self) -> list[ConfigValidationIssue]:
        issues: list[ConfigValidationIssue] = []

        if self.fixture_mode:
            issues.append(
                ConfigValidationIssue(
                    severity=(
                        ConfigIssueSeverity.ERROR
                        if self.is_production_profile
                        else ConfigIssueSeverity.WARNING
                    ),
                    code="fixture_mode_enabled",
                    message=(
                        "FIXTURE_MODE is enabled. Runtime product flows must still use live "
                        "Afferens perception; fixtures are allowed only in tests."
                    ),
                    required=self.is_production_profile,
                )
            )

        if self.database_enabled:
            if not self.database_configured:
                issues.append(
                    ConfigValidationIssue(
                        severity=(
                            ConfigIssueSeverity.ERROR
                            if self.is_production_profile
                            else ConfigIssueSeverity.WARNING
                        ),
                        code="database_url_missing",
                        message="DATABASE_URL is required for durable memory, tasks, and deployed runtime profiles.",
                        required=True,
                    )
                )
        elif self.is_production_profile:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.ERROR,
                    code="database_disabled",
                    message="DATABASE_ENABLED=false is not allowed for deployed runtime profiles.",
                    required=True,
                )
            )

        if not self.afferens_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=(
                        ConfigIssueSeverity.ERROR
                        if self.is_production_profile
                        else ConfigIssueSeverity.WARNING
                    ),
                    code="afferens_api_key_missing",
                    message="AFFERENS_API_KEY is required for live physical perception.",
                    required=True,
                )
            )

        if self.is_production_profile and not self.public_api_base_url_value:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.ERROR,
                    code="public_api_base_url_missing",
                    message="PUBLIC_API_BASE_URL must be set for deployed frontend/backend wiring.",
                    required=True,
                )
            )

        cors_origins = self.cors_allowed_origin_list
        if self.is_production_profile and not _parse_csv(self.cors_allowed_origins):
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.ERROR,
                    code="cors_origins_missing",
                    message="CORS_ALLOWED_ORIGINS must explicitly list deployed frontend origins in production.",
                    required=True,
                )
            )
        if "*" in cors_origins:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.ERROR,
                    code="cors_wildcard_origin",
                    message="CORS_ALLOWED_ORIGINS must not use '*' for this secret-bearing API.",
                    required=True,
                )
            )

        if self.langsmith_tracing and not self.langsmith_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.WARNING,
                    code="langsmith_key_missing",
                    message="LANGSMITH_TRACING=true but LANGSMITH_API_KEY is not configured; tracing is disabled.",
                )
            )

        if not self.fireworks_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.INFO,
                    code="fireworks_key_missing",
                    message="FIREWORKS_API_KEY is optional; deterministic evidence-backed fallback will be used.",
                )
            )

        if self.gemini_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.INFO,
                    code="gemini_deferred",
                    message="GEMINI_API_KEY is configured, but Gemini remains a deferred privacy-gated provider.",
                )
            )

        if self.parcle_configured or self.parcel_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.INFO,
                    code="parcle_deferred",
                    message="Parcle/Parcel keys are configured, but that memory provider is not implemented.",
                )
            )

        if self.embedding_configured:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.INFO,
                    code="embedding_provider_fallback",
                    message=(
                        "External embedding provider settings are present, but this build uses "
                        "deterministic local embeddings for hybrid pgvector-ready semantic retrieval."
                    ),
                )
            )

        if self.action_yolo_fall_enabled and not self.action_yolo_fall_model_path:
            issues.append(
                ConfigValidationIssue(
                    severity=ConfigIssueSeverity.WARNING,
                    code="yolo_model_path_missing",
                    message="ACTION_YOLO_FALL_ENABLED=true but no model path is configured; fall inference will be unavailable.",
                )
            )

        return issues


def _normalize_label_list(value: str) -> set[str]:
    return {
        item.strip().lower().replace("-", "_").replace(" ", "_")
        for item in value.split(",")
        if item.strip()
    }


def _parse_csv(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _local_cors_origins() -> list[str]:
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
