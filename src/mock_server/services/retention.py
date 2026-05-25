"""Retention: удаление просроченных archive_items."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.models import ArchiveItem


async def delete_expired(session: AsyncSession) -> int:
    """Удаляет архивные элементы с expires_at < now(). Возвращает количество удалённых."""
    now = datetime.now(UTC)
    stmt = delete(ArchiveItem).where(ArchiveItem.expires_at < now)
    result = await session.execute(stmt)
    rowcount = getattr(result, "rowcount", 0) or 0
    return int(rowcount)
