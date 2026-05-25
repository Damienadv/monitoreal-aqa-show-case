"""CRUD правил с действиями."""

from __future__ import annotations

from croniter import croniter  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mock_server.auth import require_any_authenticated
from mock_server.db import get_session
from mock_server.models import Action, Camera, Rule
from mock_server.schemas import RuleCreate, RuleRead, RuleUpdate

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


def _validate_cron(cron_expr: str | None) -> None:
    if not cron_expr:
        return
    try:
        croniter(cron_expr)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}") from e


@router.post(
    "",
    response_model=RuleRead,
    status_code=201,
    dependencies=[require_any_authenticated],
)
async def create_rule(payload: RuleCreate, session: AsyncSession = Depends(get_session)) -> Rule:
    _validate_cron(payload.schedule_cron)
    camera = await session.scalar(select(Camera).where(Camera.code == payload.camera_id))
    if camera is None:
        camera = await session.get(Camera, payload.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    rule = Rule(
        name=payload.name,
        camera_id=camera.id,
        object_type=payload.object_type,
        roi_polygon=payload.roi_polygon,
        schedule_cron=payload.schedule_cron,
        threshold=payload.threshold,
        action_mode=payload.action_mode,
        actions=[
            Action(type=a.type, order_index=a.order_index, config=a.config) for a in payload.actions
        ],
    )
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail="Duplicate rule") from e
    await session.refresh(rule, attribute_names=["actions"])
    return rule


@router.get(
    "/{rule_id}",
    response_model=RuleRead,
    dependencies=[require_any_authenticated],
)
async def get_rule(rule_id: str, session: AsyncSession = Depends(get_session)) -> Rule:
    stmt = select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    rule = await session.scalar(stmt)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put(
    "/{rule_id}",
    response_model=RuleRead,
    dependencies=[require_any_authenticated],
)
async def update_rule(
    rule_id: str, payload: RuleUpdate, session: AsyncSession = Depends(get_session)
) -> Rule:
    stmt = select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    rule = await session.scalar(stmt)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    data = payload.model_dump(exclude_unset=True)
    if "schedule_cron" in data:
        _validate_cron(data["schedule_cron"])
    for k, v in data.items():
        setattr(rule, k, v)
    await session.flush()
    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_any_authenticated],
)
async def delete_rule(rule_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    rule = await session.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
