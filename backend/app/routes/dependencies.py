from __future__ import annotations

from app.afferens_adapter import AfferensAdapter
from app.config import Settings, get_settings


def get_afferens_adapter() -> AfferensAdapter:
    return AfferensAdapter(get_settings())


def get_app_settings() -> Settings:
    return get_settings()
