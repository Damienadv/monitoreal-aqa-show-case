"""API-тесты POST /api/v1/actions/test."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_rule

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_actions_test_for_existing_rule_returns_200_with_executed_chain(
    client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Существующее правило → 200 + execution log с двумя действиями.

    Covers R-AC-01 — порядок выполнения action chain в sequential.
    """
    rule = await make_rule(db_session, action_mode="sequential")
    await db_session.commit()

    response = await client.post(
        "/api/v1/actions/test", headers=admin_headers, json={"rule_id": rule.id}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule_id"] == rule.id
    assert len(body["actions_executed"]) == 2
    assert all(a["status"] == "done" for a in body["actions_executed"])


@pytest.mark.asyncio
async def test_actions_test_for_missing_rule_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Несуществующий rule_id → 404 Problem Details."""
    response = await client.post(
        "/api/v1/actions/test",
        headers=admin_headers,
        json={"rule_id": "00000000000000000000000000000000"},
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Not Found"
