"""GET /api/v1/archive — архив с фильтрами и пагинацией."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.auth import require_any_authenticated
from mock_server.db import get_session
from mock_server.models import AlertEvent, ArchiveItem, Camera, DetectionEvent
from mock_server.schemas import PaginatedArchive

router = APIRouter(prefix="/api/v1/archive", tags=["archive"])


@router.get(
    "",
    response_model=PaginatedArchive,
    dependencies=[require_any_authenticated],
)
async def list_archive(
    camera_id: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=1_000_000),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedArchive:
    base = select(ArchiveItem)
    count_stmt = select(func.count(ArchiveItem.id))

    if camera_id is not None:
        camera = await session.scalar(select(Camera).where(Camera.code == camera_id))
        if camera is None:
            camera = await session.get(Camera, camera_id)
        if camera is None:
            return PaginatedArchive(items=[], total=0, page=page, per_page=per_page)
        base = base.where(ArchiveItem.camera_id == camera.id)
        count_stmt = count_stmt.where(ArchiveItem.camera_id == camera.id)

    if object_type is not None:
        # фильтр по object_type — пробрасываем через JOIN AlertEvent → DetectionEvent
        sub = select(DetectionEvent.id).where(DetectionEvent.object_type == object_type)
        alert_sub = select(AlertEvent.id).where(AlertEvent.detection_event_id.in_(sub))
        base = base.where(ArchiveItem.alert_event_id.in_(alert_sub))
        count_stmt = count_stmt.where(ArchiveItem.alert_event_id.in_(alert_sub))

    if from_ is not None:
        base = base.where(ArchiveItem.created_at >= from_)
        count_stmt = count_stmt.where(ArchiveItem.created_at >= from_)
    if to is not None:
        base = base.where(ArchiveItem.created_at <= to)
        count_stmt = count_stmt.where(ArchiveItem.created_at <= to)

    total = (await session.scalar(count_stmt)) or 0
    base = (
        base.order_by(ArchiveItem.created_at.desc()).limit(per_page).offset((page - 1) * per_page)
    )
    items = list((await session.scalars(base)).all())
    return PaginatedArchive.model_validate(
        {"items": items, "total": total, "page": page, "per_page": per_page}
    )
