from app.config import Settings
from app.schemas import AfferensConnectionState
from app.afferens_adapter import AfferensAdapter


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
