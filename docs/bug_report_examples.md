# Bug report examples

Три гипотетических баг-репорта в формате, который я оформил бы в Jira / Linear / TestIT. Привязки к рискам: BUG-001 → R-AC-01 (фича Monitoreal v2.4.1), BUG-002 → R-FA-02 (ROI), BUG-003 → R-AUTH-01 (auth).

---

## BUG-001 — Sequential action chain executes second action before first completes

**Severity:** Blocker
**Affects:** Monitoreal mock-api 0.1.0 (commit `c8eb448`), local Docker.
**Environment:**
- OS: Ubuntu 24.04 / WSL2
- Python 3.12.3
- Docker Compose v2.34
- DB: SQLite + aiosqlite
- API base: `http://localhost:8000`

### Steps to reproduce

1. Поднять mock-api: `make up`.
2. Создать правило с двумя actions, явно в sequential mode:
   ```bash
   curl -X POST http://localhost:8000/api/v1/rules \
     -H "X-API-Key: admin-key-dev-only" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "BUG-001 repro",
       "camera_id": "cam-01",
       "object_type": "person",
       "threshold": 0.5,
       "action_mode": "sequential",
       "actions": [
         {"type": "relay", "order_index": 0, "config": {"latency_ms": 500}},
         {"type": "audio", "order_index": 1, "config": {}}
       ]
     }'
   ```
3. Послать detection event:
   ```bash
   curl -X POST http://localhost:8000/api/v1/detections \
     -H "X-API-Key: cam-key-dev-only" \
     -H "Content-Type: application/json" \
     -d '{
       "external_id": "evt-bug001",
       "camera_id": "cam-01",
       "object_type": "person",
       "confidence": 0.9,
       "bbox": [100, 200, 50, 80],
       "occurred_at": "2026-05-25T12:00:00Z"
     }'
   ```
4. Достать `alert_event_ids[0]` из ответа, открыть детали в БД или через готовящийся `/api/v1/alerts/{id}` (если эндпоинт будет).

### Expected

`actions_executed` в AlertEvent содержит две записи в порядке `[relay, audio]`, причём `audio.executed_at` строго больше `relay.executed_at + 500ms`.

### Actual

`audio.executed_at` опережает `relay.executed_at + 500ms` примерно на 480ms, то есть actions запустились параллельно вместо последовательного выполнения. Sequential mode не работает.

### Logs / Evidence

```
[mock-api] DEBUG actions_runner: starting action_chain mode=sequential len=2
[mock-api] DEBUG actions_runner: scheduled action_id=a1 type=relay order=0 at 12:00:00.012
[mock-api] DEBUG actions_runner: scheduled action_id=a2 type=audio order=1 at 12:00:00.014  ← должно быть после relay.done
[mock-api] DEBUG actions_runner: completed action_id=a2 type=audio at 12:00:00.025
[mock-api] DEBUG actions_runner: completed action_id=a1 type=relay at 12:00:00.512
```

### Suggested root cause / fix

Гипотеза: в `src/mock_server/services/actions_runner.py::run_actions` ветка `sequential` использует `asyncio.gather` вместо последовательного `for + await`. Это типовой регресс при unify'е путей parallel и sequential через одну корутину.

Fix-предложение: убедиться, что для `mode == "sequential"` стоит `for action in ordered: results.append(await _execute_one(action))`, а не `gather`. Добавить регресс-тест: `tests/api/test_actions.py::test_sequential_mode_waits_for_previous_action_done` — мокать `_execute_one` с разными `asyncio.sleep` и проверить порядок completion'а.

**Связанный риск:** R-AC-01. Покрытие после фикса: `tests/e2e/test_multiple_actions_per_rule.py` уже проверяет порядок типов; добавить проверку **времени** между actions.

---

## BUG-002 — Detection outside ROI polygon still triggers rule

**Severity:** Major
**Affects:** mock-api 0.1.0, rules engine v1.
**Environment:** same as BUG-001.

### Steps to reproduce

1. Создать правило с ROI-полигоном, ограниченным верхним левым квадрантом кадра 640×480:
   ```bash
   curl -X POST http://localhost:8000/api/v1/rules \
     -H "X-API-Key: admin-key-dev-only" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "BUG-002 ROI upper-left",
       "camera_id": "cam-01",
       "object_type": "person",
       "threshold": 0.5,
       "action_mode": "parallel",
       "roi_polygon": [[0,0],[320,0],[320,240],[0,240]],
       "actions": [{"type": "relay", "order_index": 0, "config": {}}]
     }'
   ```
2. Послать detection с bbox в **правом нижнем** квадранте (центр в (500, 400)):
   ```bash
   curl -X POST http://localhost:8000/api/v1/detections \
     -H "X-API-Key: cam-key-dev-only" \
     -H "Content-Type: application/json" \
     -d '{
       "external_id": "evt-bug002",
       "camera_id": "cam-01",
       "object_type": "person",
       "confidence": 0.95,
       "bbox": [475, 375, 50, 50],
       "occurred_at": "2026-05-25T12:00:00Z"
     }'
   ```

### Expected

Response: `matched_rule_ids` пуст (детекция вне ROI), `alert_event_ids` пуст, тело имеет 201 с пустыми массивами.

### Actual

Response: `matched_rule_ids` содержит ID правила, `alert_event_ids` содержит ID нового alert'а. Правило сработало вопреки ROI.

### Logs / Evidence

Не хватает дебаг-лога в `rules_engine._point_in_polygon`. Для воспроизведения в pytest:

```python
from mock_server.services.rules_engine import _point_in_polygon
polygon = [[0,0],[320,0],[320,240],[0,240]]
assert _point_in_polygon((500.0, 400.0), polygon) is False  # ожидаем False
# фактически — True, точка ошибочно считается внутри
```

### Suggested root cause / fix

Гипотеза: в `_point_in_polygon` ray-casting использует условие `(yi > y) != (yj > y)`, которое для точек **строго на ребре** даёт false-positive. Для замкнутого полигона с вершинами на осях край (320, *) / (*, 240) может ошибочно считаться внутренним. Стоит покрыть property-based тестом через Hypothesis с генерацией случайных треугольников и проверкой инварианта «точка вне bbox полигона → не внутри полигона».

**Связанный риск:** R-FA-02. После фикса добавить `tests/api/test_rules_engine.py::test_point_in_polygon_excludes_edge_cases`, который сейчас не входит в scope шоукейса.

---

## BUG-003 — DELETE /api/v1/media/expired accepts viewer role and returns 200

**Severity:** Major
**Affects:** mock-api 0.1.0, auth middleware.
**Environment:** same as BUG-001.

### Steps to reproduce

1. Создать ArchiveItem с `expires_at` в прошлом (через фикстуру или прямую вставку в БД, либо через retention manipulation).
2. Послать DELETE с viewer-ключом:
   ```bash
   curl -X DELETE http://localhost:8000/api/v1/media/expired \
     -H "X-API-Key: viewer-key-dev-only" -i
   ```

### Expected

HTTP 403 Forbidden с RFC 7807 Problem Details:
```json
{
  "type": "about:blank",
  "title": "Forbidden",
  "status": 403,
  "detail": "Role 'viewer' is not allowed (need one of: admin)",
  "instance": "/api/v1/media/expired"
}
```

### Actual

HTTP 200 OK + `{"deleted": N}`. Viewer успешно удалил данные, что нарушает RBAC.

### Logs / Evidence

```
INFO:     127.0.0.1:51234 - "DELETE /api/v1/media/expired HTTP/1.1" 200 OK
```

Никаких WARNING про auth — middleware пропустил запрос без проверки роли.

### Suggested root cause / fix

Гипотеза: эндпоинт DELETE объявлен с `dependencies=[require_any_authenticated]` вместо `[require_admin]`. Проверить `src/mock_server/routers/media.py` (или `retention.py`) — какой dependency у DELETE.

Fix: заменить на `Depends(require_role("admin"))` либо использовать готовый `require_admin` из `mock_server.auth`. Добавить тест-страж: `tests/api/test_retention.py::test_delete_expired_rejects_viewer_role` — viewer-headers → 403.

**Связанный риск:** R-AUTH-01. Сейчас покрыт `tests/api/test_retention.py::test_delete_expired_requires_admin_role`, но именно этот тест и должен был поймать этот баг — нужно проверить, что он действительно валидирует **403** на viewer, а не просто «не-admin даёт не-200».

---

## Связи

- `docs/risk_matrix.md` — все три бага привязаны к рискам.
- `docs/test_strategy.md` §3 — как риски учтены в стратегии.
