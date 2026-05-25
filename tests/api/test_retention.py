"""API-тесты DELETE /api/v1/media/expired — auth + boundary."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import get_camera_by_code, make_alert_with_archive

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_delete_expired_from_viewer_returns_403(
    client: AsyncClient, viewer_headers: dict[str, str]
) -> None:
    """Viewer не может вызывать retention.

    Covers R-AUTH-01 — role check на admin-only эндпоинте.
    """
    response = await client.delete("/api/v1/media/expired", headers=viewer_headers)
    assert response.status_code == 403
    body = response.json()
    assert body["status"] == 403
    assert body["title"] == "Forbidden"


@pytest.mark.asyncio
async def test_delete_expired_from_admin_removes_only_expired_items(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Admin → удаляются только записи с expires_at < now(), свежие остаются.

    Covers R-RET-01 (DELETE /media/expired удаляет не-expired items).
    """
    cam = await get_camera_by_code(db_session)
    await make_alert_with_archive(db_session, camera=cam, expires_in=timedelta(days=-1))
    await make_alert_with_archive(db_session, camera=cam, expires_in=timedelta(days=-2))
    await make_alert_with_archive(db_session, camera=cam, expires_in=timedelta(days=30))
    await db_session.commit()

    response = await client.delete("/api/v1/media/expired", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] == 2

    # Свежий — на месте: проверка через /archive
    remaining = await client.get("/api/v1/archive", headers=admin_headers)
    assert remaining.json()["total"] == 1
