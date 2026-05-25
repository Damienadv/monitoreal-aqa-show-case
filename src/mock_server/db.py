"""SQLAlchemy async engine + сессии. Декларативная база для моделей."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from mock_server.config import get_settings


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


def make_engine(database_url: str | None = None) -> AsyncEngine:
    """Сборка async engine. Принимает URL для override'ов в тестах."""
    url = database_url or get_settings().database_url
    # check_same_thread нужен для in-memory SQLite в тестах;
    # для aiosqlite это безопасно — pool по умолчанию NullPool.
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(url, echo=False, future=True, connect_args=connect_args)


engine: AsyncEngine = make_engine()
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends — отдаёт сессию с авто-rollback при ошибке."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Альтернатива get_session — для использования вне FastAPI (lifespan, seed, скрипты)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
