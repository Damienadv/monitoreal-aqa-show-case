"""GET /api/v1/events — список alert_events с фильтрами и пагинацией."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.auth import require_any_authenticated
from mock_server.db import get_session
from mock_server.models import AlertEvent, Camera
from mock_server.schemas import PaginatedAlertEvents

router = APIRouter(prefix="/api/v1/events", tags=["detections"])


@router.get(
    "",
    response_model=PaginatedAlertEvents,
    dependencies=[require_any_authenticated],
)
async def list_events(
    camera_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=1_000_000),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedAlertEvents:
    base = select(AlertEvent)
    count_stmt = select(func.count(AlertEvent.id))

    if camera_id is not None:
        # camera_id фильтр через alert_events.rule.camera — но проще: фильтруем по
        # связке alert_event.detection_event.camera_id; для простоты — через подзапрос rules.
        from mock_server.models import Rule

        camera = await session.scalar(select(Camera).where(Camera.code == camera_id))
        if camera is None:
            camera = await session.get(Camera, camera_id)
        if camera is not None:
            sub = select(Rule.id).where(Rule.camera_id == camera.id)
            base = base.where(AlertEvent.rule_id.in_(sub))
            count_stmt = count_stmt.where(AlertEvent.rule_id.in_(sub))
        else:
            return PaginatedAlertEvents(items=[], total=0, page=page, per_page=per_page)

    if status is not None:
        base = base.where(AlertEvent.status == status)
        count_stmt = count_stmt.where(AlertEvent.status == status)

    total = (await session.scalar(count_stmt)) or 0
    base = base.order_by(AlertEvent.created_at.desc()).limit(per_page).offset((page - 1) * per_page)
    items = list((await session.scalars(base)).all())
    return PaginatedAlertEvents.model_validate(
        {"items": items, "total": total, "page": page, "per_page": per_page}
    )
