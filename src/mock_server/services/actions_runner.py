"""Mock-исполнение действий (relay/audio/mobile_push/webhook)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from mock_server.models import Action


async def _execute_one(action: Action) -> dict[str, Any]:
    """Mock-исполнение: лёгкий sleep + статус done. Реальные эффекты — out of scope mock'а."""
    await asyncio.sleep(0.01)
    return {
        "action_id": action.id,
        "type": action.type,
        "status": "done",
        "executed_at": datetime.now(UTC).isoformat(),
        "error": None,
    }


async def run_actions(actions: list[Action], mode: str) -> list[dict[str, Any]]:
    """Запускает действия в parallel или sequential режиме."""
    if not actions:
        return []
    ordered = sorted(actions, key=lambda a: a.order_index)
    if mode == "parallel":
        return list(await asyncio.gather(*(_execute_one(a) for a in ordered)))
    # sequential
    results: list[dict[str, Any]] = []
    for action in ordered:
        results.append(await _execute_one(action))
    return results
