"""Rules engine: matched rules для пришедшего detection event."""

from __future__ import annotations

from datetime import datetime

from croniter import croniter  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mock_server.models import DetectionEvent, Rule


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    """Ray casting. Возвращает True если точка внутри полигона."""
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def _bbox_center(bbox: list[int]) -> tuple[float, float]:
    x, y, w, h = bbox
    return (x + w / 2, y + h / 2)


def _matches_schedule(rule_cron: str | None, when: datetime) -> bool:
    if not rule_cron:
        return True
    # croniter.match — есть, но через iterator проще и явнее.
    try:
        # croniter.match возвращает bool — оборачиваем явно для mypy
        return bool(croniter.match(rule_cron, when))
    except Exception:
        return False


async def find_matching_rules(session: AsyncSession, event: DetectionEvent) -> list[Rule]:
    """Найти все enabled rules для камеры события, удовлетворяющие условиям."""
    stmt = (
        select(Rule)
        .where(Rule.camera_id == event.camera_id, Rule.is_enabled.is_(True))
        .options(selectinload(Rule.actions))
    )
    rules = (await session.scalars(stmt)).all()

    matched: list[Rule] = []
    for rule in rules:
        if rule.object_type != event.object_type and rule.object_type != "unknown":
            continue
        if event.confidence < rule.threshold:
            continue
        if (
            rule.roi_polygon
            and event.bbox is not None
            and not _point_in_polygon(_bbox_center(event.bbox), rule.roi_polygon)
        ):
            continue
        if not _matches_schedule(rule.schedule_cron, event.occurred_at):
            continue
        matched.append(rule)
    return matched
