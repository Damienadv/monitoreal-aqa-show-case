"""POST /api/v1/actions/test — тестовый запуск action chain существующего правила."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mock_server.auth import require_any_authenticated
from mock_server.db import get_session
from mock_server.models import Rule
from mock_server.schemas import ActionsTestRequest, ActionsTestResponse
from mock_server.services.actions_runner import run_actions

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


@router.post(
    "/test",
    response_model=ActionsTestResponse,
    dependencies=[require_any_authenticated],
)
async def test_actions(
    payload: ActionsTestRequest, session: AsyncSession = Depends(get_session)
) -> ActionsTestResponse:
    stmt = select(Rule).where(Rule.id == payload.rule_id).options(selectinload(Rule.actions))
    rule = await session.scalar(stmt)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    executed = await run_actions(rule.actions, rule.action_mode)
    return ActionsTestResponse.model_validate({"rule_id": rule.id, "actions_executed": executed})
