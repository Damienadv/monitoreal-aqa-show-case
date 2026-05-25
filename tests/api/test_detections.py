"""API-тесты POST /api/v1/detections — happy / negative / idempotency."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import detection_payload, make_rule

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_post_detection_returns_201_and_matches_enabled_rule(
    client: AsyncClient, camera_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Happy path: detection попадает в правило, создаётся alert + archive item.

    Covers R-FA-01 (false-alert from low confidence) — sanity на матчинг по threshold.
    See: docs/risk_matrix.md
    """
    rule = await make_rule(db_session, object_type="person", action_mode="parallel")
    await db_session.commit()

    response = await client.post(
        "/api/v1/detections",
        headers=camera_headers,
        json=detection_payload(external_id="evt-positive", confidence=0.9),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert rule.id in body["matched_rule_ids"]
    assert len(body["alert_event_ids"]) == 1


@pytest.mark.asyncio
async def test_post_detection_returns_404_when_camera_not_found(
    client: AsyncClient, camera_headers: dict[str, str]
) -> None:
    """Неизвестный camera_id → 404 Problem Details.

    Covers R-FA-* sanity — unknown source should be rejected.
    """
    response = await client.post(
        "/api/v1/detections",
        headers=camera_headers,
        json=detection_payload(camera_code="cam-nonexistent"),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"


@pytest.mark.asyncio
async def test_post_detection_is_idempotent_on_duplicate_external_id(
    client: AsyncClient, camera_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Дубликат external_id → 200 (вместо 201), без повторного срабатывания правил.

    Covers R-FA-03 (duplicate detection creates second alert and re-triggers actions).
    """
    await make_rule(db_session, object_type="person", action_mode="sequential")
    await db_session.commit()

    payload = detection_payload(external_id="evt-dup-001", confidence=0.95)

    first = await client.post("/api/v1/detections", headers=camera_headers, json=payload)
    assert first.status_code == 201
    first_body = first.json()

    second = await client.post("/api/v1/detections", headers=camera_headers, json=payload)
    assert second.status_code == 200, second.text
    second_body = second.json()

    assert second_body["duplicate"] is True
    assert second_body["detection_event_id"] == first_body["detection_event_id"]
    assert second_body["alert_event_ids"] == first_body["alert_event_ids"]
