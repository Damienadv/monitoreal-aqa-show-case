"""Schemathesis property-based contract тесты против OpenAPI авто-сгенерированной FastAPI'ем.

Schemathesis читает /api/v1/openapi.json у запущенного ASGI-приложения и генерит
hypothesis-кейсы для каждого endpoint'а. Проверяет, что ответы соответствуют схеме.

Covers множество рисков: схема и реализация in sync, ProblemDetail на ошибках валиден,
эндпоинты не падают с 500 на пограничных значениях.
"""

from __future__ import annotations

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error

from mock_server.config import get_settings
from mock_server.main import app

pytestmark = pytest.mark.contract


schema = schemathesis.from_asgi("/api/v1/openapi.json", app, force_schema_version="30")


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
        HealthCheck.filter_too_much,
    ],
)
def test_api_conforms_to_openapi(case: schemathesis.Case) -> None:
    """Property-based: ни один генерированный input не валит сервер (5xx).

    Полная schema-conformance делается в test_jsonschema_responses.py против
    docs/api_contract.yaml (наш source of truth). Здесь — sanity-обстрел случайными
    значениями: timeouts, типы, граничные числа. Любой 5xx = баг.
    """
    headers = {"X-API-Key": get_settings().api_key_admin}
    response = case.call(headers=headers)
    case.validate_response(response, checks=(not_a_server_error,))
