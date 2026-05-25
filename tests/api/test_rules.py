"""API-тесты CRUD правил."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_create_rule_with_two_actions_returns_201(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Создание правила с двумя действиями в sequential mode.

    Covers R-AC-01 (in sequential mode actions execute in parallel) — sanity на хранение order.
    """
    payload = {
        "name": "Person after 22:00",
        "camera_id": "cam-01",
        "object_type": "person",
        "threshold": 0.7,
        "action_mode": "sequential",
        "actions": [
            {"type": "relay", "order_index": 0, "config": {"relay_id": 1}},
            {"type": "audio", "order_index": 1, "config": {"sound": "alarm.wav"}},
        ],
    }
    response = await client.post("/api/v1/rules", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Person after 22:00"
    assert len(body["actions"]) == 2
    assert [a["type"] for a in body["actions"]] == ["relay", "audio"]
    assert [a["order_index"] for a in body["actions"]] == [0, 1]


@pytest.mark.asyncio
async def test_create_rule_with_empty_actions_returns_422(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Пустой список actions → 422 Pydantic validation.

    Covers R-AC-02 — правило без действий не должно создаваться.
    """
    payload = {
        "name": "Empty actions",
        "camera_id": "cam-01",
        "object_type": "person",
        "action_mode": "parallel",
        "actions": [],
    }
    response = await client.post("/api/v1/rules", headers=admin_headers, json=payload)
    assert response.status_code == 422
    assert response.json()["status"] == 422


@pytest.mark.asyncio
async def test_create_rule_with_invalid_cron_returns_400(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Невалидный schedule_cron → 400 Bad Request.

    Covers R-FA-01 (rules with broken schedule could mis-fire).
    """
    payload = {
        "name": "Bad cron",
        "camera_id": "cam-01",
        "object_type": "person",
        "schedule_cron": "not a cron at all",
        "action_mode": "parallel",
        "actions": [{"type": "relay", "order_index": 0}],
    }
    response = await client.post("/api/v1/rules", headers=admin_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == 400
    assert "cron" in (body.get("detail") or "").lower()
