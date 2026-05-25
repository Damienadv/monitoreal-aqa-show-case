"""GET /api/v1/cameras — список камер."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.auth import require_any_authenticated
from mock_server.db import get_session
from mock_server.models import Camera
from mock_server.schemas import CameraRead

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraRead], dependencies=[require_any_authenticated])
async def list_cameras(session: AsyncSession = Depends(get_session)) -> list[Camera]:
    return list((await session.scalars(select(Camera).order_by(Camera.code))).all())
