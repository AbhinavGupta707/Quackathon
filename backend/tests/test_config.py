from app.config import Settings
from app.observability import langsmith_status, sanitize_for_trace
from app.schemas import AfferensConnectionState
from app.afferens_adapter import AfferensAdapter
from app.main import create_app


async def test_missing_key_status_does_not_include_secret() -> None:
    settings = Settings(afferens_api_key=None)
    result = await AfferensAdapter(settings).fetch_latest()

    status = result.status.model_dump(mode="json")

    assert status["configured"] is False
    assert status["state"] == AfferensConnectionState.MISSING_KEY
    assert "api_key" not in status
    assert "key" not in status["message"].lower() or "configured" in status["message"].lower()


def test_settings_secret_repr_does_not_reveal_value() -> None:
    settings = Settings(afferens_api_key="real-secret-value")

    rendered = repr(settings)

    assert "real-secret-value" not in rendered
    assert settings.afferens_configured is True


def test_afferens_actuation_defaults_to_safe_disabled_state() -> None:
    settings = Settings()

    assert settings.afferens_actuation_enabled is False
    assert settings.afferens_supported_actuation_commands == {
        "TRIGGER_ALARM",
        "CAPTURE_FRAME",
    }


def test_action_adapter_defaults_to_telemetry_only_without_raw_video() -> None:
    settings = Settings(
        action_yolo_fall_enabled=False,
        action_yolo_fall_model_path=None,
        action_raw_video_storage_enabled=False,
    )

    assert settings.action_yolo_fall_enabled is False
    assert settings.action_yolo_fall_model_path is None
    assert settings.action_fall_persistence_seconds == 3.5
    assert settings.action_fall_debounce_seconds == 120
    assert settings.action_drink_min_window_seconds == 1.0
    assert settings.action_raw_video_storage_enabled is False


def test_langsmith_is_optional_and_secret_safe() -> None:
    disabled = Settings(langsmith_tracing=False, langsmith_api_key=None)
    enabled = Settings(langsmith_tracing=True, langsmith_api_key="langsmith-secret")

    assert disabled.langsmith_runtime_enabled is False
    assert enabled.langsmith_runtime_enabled is True
    assert "langsmith-secret" not in repr(enabled)
    assert langsmith_status(disabled).state == "degraded"
    assert langsmith_status(enabled).state == "ok"


def test_langsmith_trace_sanitizer_omits_sensitive_content_by_default() -> None:
    sanitized = sanitize_for_trace(
        {
            "query": "Where are my keys?",
            "api_key": "secret-key",
            "messages": [{"content": "private patient text"}],
            "metadata": {"object_key": "keys"},
        },
        include_content=False,
    )

    assert sanitized["query"] == "[content omitted]"
    assert sanitized["api_key"] == "[redacted]"
    assert sanitized["messages"] == "[content omitted]"
    assert sanitized["metadata"]["object_key"] == "keys"


def test_development_cors_defaults_keep_local_dev_ergonomic() -> None:
    settings = Settings(environment="development")

    assert "http://localhost:3000" in settings.cors_allowed_origin_list
    assert "http://127.0.0.1:3000" in settings.cors_allowed_origin_list


def test_production_startup_validation_requires_deploy_boundary() -> None:
    settings = Settings(
        environment="production",
        afferens_api_key=None,
        database_url=None,
        public_api_base_url=None,
        cors_allowed_origins="",
    )
    issues = {issue.code: issue for issue in settings.validate_startup_environment()}

    assert issues["afferens_api_key_missing"].severity == "error"
    assert issues["database_url_missing"].severity == "error"
    assert issues["public_api_base_url_missing"].severity == "error"
    assert issues["cors_origins_missing"].severity == "error"


def test_production_startup_rejects_wildcard_cors() -> None:
    settings = Settings(
        environment="production",
        afferens_api_key="secret-afferens",
        database_url="postgresql+psycopg://user:pass@db.example/guardian",
        public_api_base_url="https://api.example.com",
        cors_allowed_origins="*",
    )
    issues = {issue.code: issue for issue in settings.validate_startup_environment()}

    assert issues["cors_wildcard_origin"].severity == "error"
    try:
        create_app(settings)
    except RuntimeError as exc:
        assert "cors_wildcard_origin" in str(exc)
        assert "secret-afferens" not in str(exc)
    else:
        raise AssertionError("Production wildcard CORS must fail startup validation")


def test_production_cors_only_allows_configured_origins() -> None:
    app = create_app(
        Settings(
            environment="production",
            afferens_api_key="secret-afferens",
            database_url="postgresql+psycopg://user:pass@db.example/guardian",
            public_api_base_url="https://api.example.com",
            cors_allowed_origins="https://memory.example.com",
        )
    )
    from fastapi.testclient import TestClient

    client = TestClient(app)
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "https://memory.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://memory.example.com"
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers
