"""POST /api/v1/detections — приём событий детекции с идемпотентностью."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mock_server.auth import require_any_authenticated
from mock_server.config import get_settings
from mock_server.db import get_session
from mock_server.models import AlertEvent, ArchiveItem, Camera, DetectionEvent, Rule
from mock_server.schemas import DetectionAccepted, DetectionEventCreate
from mock_server.services.actions_runner import run_actions
from mock_server.services.rules_engine import find_matching_rules

router = APIRouter(prefix="/api/v1/detections", tags=["detections"])


async def _process_rules_for_detection(session: AsyncSession, event: DetectionEvent) -> list[str]:
    """Применяет rules engine + actions runner. Создаёт AlertEvent и ArchiveItem."""
    matched: list[Rule] = await find_matching_rules(session, event)
    alert_event_ids: list[str] = []
    retention = timedelta(days=get_settings().archive_retention_days)

    for rule in matched:
        executed: list[dict[str, Any]] = await run_actions(rule.actions, rule.action_mode)
        alert = AlertEvent(
            detection_event_id=event.id,
            rule_id=rule.id,
            status="done",
            actions_executed=executed,
        )
        session.add(alert)
        await session.flush()
        archive = ArchiveItem(
            alert_event_id=alert.id,
            camera_id=event.camera_id,
            snapshot_url=f"/media/snapshots/{alert.id}.jpg",
            meta={
                "object_type": event.object_type,
                "confidence": event.confidence,
                "rule_name": rule.name,
            },
            expires_at=datetime.now(UTC) + retention,
        )
        session.add(archive)
        alert_event_ids.append(alert.id)

    return alert_event_ids


@router.post(
    "",
    response_model=DetectionAccepted,
    dependencies=[require_any_authenticated],
)
async def post_detection(
    payload: DetectionEventCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> DetectionAccepted:
    # camera lookup по code или id
    camera = await session.scalar(select(Camera).where(Camera.code == payload.camera_id))
    if camera is None:
        camera = await session.get(Camera, payload.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # idempotency: (external_id, camera_id)
    existing = await session.scalar(
        select(DetectionEvent).where(
            DetectionEvent.external_id == payload.external_id,
            DetectionEvent.camera_id == camera.id,
        )
    )
    if existing is not None:
        existing_alerts = await session.scalars(
            select(AlertEvent).where(AlertEvent.detection_event_id == existing.id)
        )
        alert_ids = [a.id for a in existing_alerts.all()]
        rule_ids = list(
            await session.scalars(
                select(AlertEvent.rule_id).where(AlertEvent.detection_event_id == existing.id)
            )
        )
        response.status_code = 200
        return DetectionAccepted(
            detection_event_id=existing.id,
            matched_rule_ids=rule_ids,
            alert_event_ids=alert_ids,
            duplicate=True,
        )

    event = DetectionEvent(
        external_id=payload.external_id,
        camera_id=camera.id,
        object_type=payload.object_type,
        confidence=payload.confidence,
        bbox=payload.bbox,
        occurred_at=payload.occurred_at,
    )
    session.add(event)
    await session.flush()

    # rules engine + actions runner
    stmt = (
        select(Rule)
        .where(Rule.camera_id == camera.id, Rule.is_enabled.is_(True))
        .options(selectinload(Rule.actions))
    )
    await session.scalars(stmt)  # eager-load for use later
    matched = await find_matching_rules(session, event)
    matched_ids = [r.id for r in matched]

    alert_ids = await _process_rules_for_detection(session, event)

    response.status_code = status.HTTP_201_CREATED
    return DetectionAccepted(
        detection_event_id=event.id,
        matched_rule_ids=matched_ids,
        alert_event_ids=alert_ids,
        duplicate=False,
    )
