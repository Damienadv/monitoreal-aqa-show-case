"""DELETE /api/v1/media/expired — retention (admin-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.auth import require_admin
from mock_server.db import get_session
from mock_server.schemas import RetentionResponse
from mock_server.services.retention import delete_expired

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.delete("/expired", response_model=RetentionResponse, dependencies=[require_admin])
async def delete_expired_media(
    session: AsyncSession = Depends(get_session),
) -> RetentionResponse:
    count = await delete_expired(session)
    return RetentionResponse(deleted_count=count)
