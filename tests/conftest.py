"""Общие фикстуры pytest: in-memory SQLite, FastAPI app, httpx-клиент, фабрики."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mock_server import db as db_module
from mock_server.config import get_settings
from mock_server.db import make_engine
from mock_server.main import app as fastapi_app
from mock_server.main import seed_cameras
from mock_server.models import Base


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[None]:
    """Свежий in-memory SQLite на каждый тест — полная изоляция."""
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    original_engine = db_module.engine
    original_sessionmaker = db_module.AsyncSessionLocal
    db_module.engine = engine
    db_module.AsyncSessionLocal = SessionLocal

    # seed cam-01/cam-02 в свежей БД
    await seed_cameras()

    try:
        yield
    finally:
        db_module.engine = original_engine
        db_module.AsyncSessionLocal = original_sessionmaker
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: None) -> AsyncIterator[AsyncSession]:
    """Сессия для прямого доступа к БД из теста (assert-проверки состояния)."""
    async with db_module.AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def app(db_engine: None):  # type: ignore[no-untyped-def]
    return fastapi_app


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """HTTP-клиент без сети — через ASGITransport. Lifespan включён для seed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def api_key_admin() -> str:
    return get_settings().api_key_admin


@pytest.fixture
def api_key_viewer() -> str:
    return get_settings().api_key_viewer


@pytest.fixture
def api_key_camera() -> str:
    return get_settings().api_key_camera


@pytest.fixture
def admin_headers(api_key_admin: str) -> dict[str, str]:
    return {"X-API-Key": api_key_admin}


@pytest.fixture
def viewer_headers(api_key_viewer: str) -> dict[str, str]:
    return {"X-API-Key": api_key_viewer}


@pytest.fixture
def camera_headers(api_key_camera: str) -> dict[str, str]:
    return {"X-API-Key": api_key_camera}
