"""Inline-проверки реальных ответов API против схем из docs/api_contract.yaml.

В отличие от Schemathesis (который читает auto-сгенерированную FastAPI'ем OpenAPI),
здесь мы валидируем против hand-written контракта — источника правды для интеграций.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import detection_payload, make_alert_with_archive, make_rule

pytestmark = pytest.mark.contract

CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "api_contract.yaml"


def _load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open() as f:
        return yaml.safe_load(f)


def _resolve_schema(contract: dict[str, Any], schema_name: str) -> dict[str, Any]:
    """Вернуть schema из components с inlined $ref'ами через jsonschema RefResolver."""
    schema: dict[str, Any] = contract["components"]["schemas"][schema_name]
    return schema


def _validator(contract: dict[str, Any], schema_name: str) -> jsonschema.Draft202012Validator:
    """Validator с базовым store для разрешения $ref'ов на другие компоненты."""
    schema = _resolve_schema(contract, schema_name)
    # OpenAPI ref'ы такие: #/components/schemas/X — jsonschema их понимает.
    resolver = jsonschema.RefResolver.from_schema(contract)
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


@pytest.mark.asyncio
async def test_post_detections_response_matches_contract(
    client: AsyncClient, camera_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """POST /detections (201) — тело ответа валидно по схеме DetectionAccepted."""
    await make_rule(db_session, action_mode="parallel")
    await db_session.commit()

    response = await client.post(
        "/api/v1/detections", headers=camera_headers, json=detection_payload()
    )
    assert response.status_code == 201

    contract = _load_contract()
    validator = _validator(contract, "DetectionAccepted")
    validator.validate(response.json())


@pytest.mark.asyncio
async def test_get_archive_response_matches_paginated_schema(
    client: AsyncClient, viewer_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """GET /archive (200) — тело валидно по схеме PaginatedArchive (даже пустое)."""
    from tests.factories import get_camera_by_code

    cam = await get_camera_by_code(db_session)
    await make_alert_with_archive(db_session, camera=cam)
    await db_session.commit()

    response = await client.get("/api/v1/archive", headers=viewer_headers)
    assert response.status_code == 200

    contract = _load_contract()
    validator = _validator(contract, "PaginatedArchive")
    validator.validate(response.json())
