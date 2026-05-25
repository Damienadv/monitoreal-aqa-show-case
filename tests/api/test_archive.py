"""API-тесты GET /api/v1/archive — пагинация и фильтры."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import get_camera_by_code, make_alert_with_archive

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_archive_pagination_per_page_2_page_2(
    client: AsyncClient, viewer_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """5 элементов → per_page=2, page=2 → ровно 2 элемента, total=5.

    Covers R-LO-01 — sanity на корректный подсчёт total и offset.
    """
    cam = await get_camera_by_code(db_session)
    for _ in range(5):
        await make_alert_with_archive(db_session, camera=cam)
    await db_session.commit()

    response = await client.get("/api/v1/archive?per_page=2&page=2", headers=viewer_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["per_page"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_archive_filter_by_camera_id_returns_only_matching(
    client: AsyncClient, viewer_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Фильтр по camera_id отдаёт только из соответствующей камеры.

    Covers R-LO-01 — поиск событий по конкретной камере.
    """
    cam1 = await get_camera_by_code(db_session, code="cam-01")
    cam2 = await get_camera_by_code(db_session, code="cam-02")
    await make_alert_with_archive(db_session, camera=cam1)
    await make_alert_with_archive(db_session, camera=cam1)
    await make_alert_with_archive(db_session, camera=cam2)
    await db_session.commit()

    response = await client.get("/api/v1/archive?camera_id=cam-01", headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["camera_id"] == cam1.id


@pytest.mark.asyncio
async def test_archive_filter_by_date_range_boundary(
    client: AsyncClient, viewer_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Boundary-фильтр по from/to: события вне диапазона отсекаются.

    Covers R-RET-02 (timezone-aware boundary on retention dates).
    """
    cam = await get_camera_by_code(db_session)
    await make_alert_with_archive(db_session, camera=cam)
    await db_session.commit()

    future_from = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = await client.get(
        "/api/v1/archive", params={"from": future_from}, headers=viewer_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
