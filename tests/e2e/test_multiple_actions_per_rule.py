"""E2E flagship: detection → правило с 4 действиями → sequential выполнение → archive.

Отсылка к Monitoreal v2.4.1 (2026-05-22): добавлен Multiple Actions per Rule.
Этот тест — главный демо-сценарий проекта, упоминается в README/cover letter.

Сценарий полного цикла:
  1. Создаём правило с 4 actions (relay, audio, mobile_push, webhook) в sequential mode.
  2. POST /api/v1/detections — соответствующее событие.
  3. Бэк прогоняет rules engine → actions runner → создаёт AlertEvent + ArchiveItem.
  4. Проверяем что все 4 действия выполнены в правильном порядке.
  5. Проверяем что archive item доступен через GET /api/v1/archive.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mock_server.models import AlertEvent, ArchiveItem
from tests.factories import detection_payload, make_rule

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_detection_triggers_rule_with_4_sequential_actions_and_creates_archive(
    client: AsyncClient,
    camera_headers: dict[str, str],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Flagship e2e: правило с 4 действиями sequential, проверка порядка и архива.

    Covers R-AC-01 (Multiple Actions per Rule — основной use case Monitoreal v2.4.1).
    See: docs/risk_matrix.md.
    """
    rule = await make_rule(
        db_session,
        name="E2E flagship: 4 sequential actions",
        object_type="person",
        action_mode="sequential",
        threshold=0.7,
        actions=[("relay", 0), ("audio", 1), ("mobile_push", 2), ("webhook", 3)],
    )
    rule_id = rule.id
    await db_session.commit()
    expected_order = ["relay", "audio", "mobile_push", "webhook"]

    response = await client.post(
        "/api/v1/detections",
        headers=camera_headers,
        json=detection_payload(external_id="e2e-flagship-001", confidence=0.92),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert rule_id in body["matched_rule_ids"], "rule должно matchнуться"
    assert len(body["alert_event_ids"]) == 1, "ровно один alert на одно detection"
    alert_id = body["alert_event_ids"][0]

    alert_row = await db_session.execute(
        select(AlertEvent.status, AlertEvent.rule_id, AlertEvent.actions_executed).where(
            AlertEvent.id == alert_id
        )
    )
    alert = alert_row.one_or_none()
    assert alert is not None, "AlertEvent должен быть persisted"
    status_val, alert_rule_id, actions_executed = alert
    assert status_val == "done"
    assert alert_rule_id == rule_id

    executed_types = [a["type"] for a in actions_executed]
    assert executed_types == expected_order, (
        f"sequential mode → порядок actions должен совпадать с order_index. "
        f"Ожидалось {expected_order}, получено {executed_types}"
    )
    assert all(a["status"] == "done" for a in actions_executed), (
        "все 4 действия должны быть в статусе done"
    )

    archive_id = await db_session.scalar(
        select(ArchiveItem.id).where(ArchiveItem.alert_event_id == alert_id)
    )
    assert archive_id is not None, "ArchiveItem должен создаться автоматически"

    list_response = await client.get(
        "/api/v1/archive",
        headers=admin_headers,
        params={"camera_id": "cam-01"},
    )
    assert list_response.status_code == 200
    archive_ids = [item["id"] for item in list_response.json()["items"]]
    assert archive_id in archive_ids, (
        "созданный archive item должен возвращаться через GET /api/v1/archive"
    )
