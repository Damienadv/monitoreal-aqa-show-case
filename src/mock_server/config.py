"""Конфигурация приложения через переменные окружения.

Pydantic Settings читает .env при локальном запуске; в Docker — env_file из compose.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса. Все поля имеют дефолты — приложение стартует и без .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./data/mock.db"

    api_key_camera: str = "cam-key-dev-only"
    api_key_viewer: str = "viewer-key-dev-only"
    api_key_admin: str = "admin-key-dev-only"

    archive_retention_days: int = 30
    webhook_sink_url: str = "http://localhost:8001"

    @property
    def api_keys(self) -> dict[str, str]:
        """Маппинг API-ключ → роль."""
        return {
            self.api_key_camera: "camera",
            self.api_key_viewer: "viewer",
            self.api_key_admin: "admin",
        }


@lru_cache
def get_settings() -> Settings:
    """Кешированный синглтон настроек (lifetime приложения)."""
    return Settings()
