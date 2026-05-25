"""Фабрики тестовых данных — без factory_boy, нативные async-функции для простоты."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.models import Action, AlertEvent, ArchiveItem, Camera, DetectionEvent, Rule


async def get_camera_by_code(session: AsyncSession, code: str = "cam-01") -> Camera:
    cam = await session.scalar(select(Camera).where(Camera.code == code))
    assert cam is not None, f"Камера {code} должна быть seed'ена в conftest"
    return cam


async def make_rule(
    session: AsyncSession,
    *,
    camera: Camera | None = None,
    name: str = "Person rule",
    object_type: str = "person",
    action_mode: str = "sequential",
    threshold: float = 0.5,
    actions: list[tuple[str, int]] | None = None,
    schedule_cron: str | None = None,
    roi_polygon: list[list[float]] | None = None,
) -> Rule:
    if camera is None:
        camera = await get_camera_by_code(session)
    actions_pairs = actions or [("relay", 0), ("audio", 1)]
    rule = Rule(
        name=name,
        camera_id=camera.id,
        object_type=object_type,
        roi_polygon=roi_polygon,
        schedule_cron=schedule_cron,
        threshold=threshold,
        action_mode=action_mode,
        actions=[Action(type=t, order_index=i, config={}) for t, i in actions_pairs],
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule, attribute_names=["actions"])
    return rule


def detection_payload(
    *,
    external_id: str = "evt-001",
    camera_code: str = "cam-01",
    object_type: str = "person",
    confidence: float = 0.95,
    bbox: list[int] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "camera_id": camera_code,
        "object_type": object_type,
        "confidence": confidence,
        "bbox": bbox if bbox is not None else [100, 200, 50, 80],
        "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
    }


async def make_archive_item(
    session: AsyncSession,
    *,
    camera: Camera,
    alert_event: AlertEvent,
    expires_in: timedelta = timedelta(days=30),
    object_type: str = "person",
) -> ArchiveItem:
    item = ArchiveItem(
        alert_event_id=alert_event.id,
        camera_id=camera.id,
        snapshot_url=f"/media/snapshots/{alert_event.id}.jpg",
        meta={"object_type": object_type, "confidence": 0.9},
        expires_at=datetime.now(UTC) + expires_in,
    )
    session.add(item)
    await session.flush()
    return item


async def make_alert_with_archive(
    session: AsyncSession,
    *,
    camera: Camera | None = None,
    rule: Rule | None = None,
    object_type: str = "person",
    expires_in: timedelta = timedelta(days=30),
) -> tuple[AlertEvent, ArchiveItem]:
    if camera is None:
        camera = await get_camera_by_code(session)
    if rule is None:
        rule = await make_rule(session, camera=camera, object_type=object_type)

    det = DetectionEvent(
        external_id=f"evt-{rule.id[:6]}",
        camera_id=camera.id,
        object_type=object_type,
        confidence=0.9,
        bbox=[10, 20, 30, 40],
        occurred_at=datetime.now(UTC),
    )
    session.add(det)
    await session.flush()

    alert = AlertEvent(
        detection_event_id=det.id, rule_id=rule.id, status="done", actions_executed=[]
    )
    session.add(alert)
    await session.flush()

    archive = await make_archive_item(
        session,
        camera=camera,
        alert_event=alert,
        expires_in=expires_in,
        object_type=object_type,
    )
    return alert, archive
