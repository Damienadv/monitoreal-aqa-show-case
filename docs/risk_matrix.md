# Risk matrix

Риски гипотетического Edge AI surveillance сервиса и какие тесты их закрывают.

ID имеют формат `R-<CAT>-<NN>`. CAT: FA (false alerts), LO (loss of event), AC (action chain), RET (retention), AUTH (auth), PRIV (privacy). Likelihood / Impact оценены для камеры у бизнес-клиента. Колонка **Tests** — путь к тесту или явное `TODO: not covered`.

## Сводная таблица

| ID | Category | Risk description | Likelihood | Impact | Tests |
|---|---|---|---|---|---|
| **R-FA-01** | False alerts | Detection с confidence ниже threshold правила всё-таки создаёт alert. | Medium | Critical | `tests/api/test_detections.py::test_post_detection_returns_201_and_matches_enabled_rule`, `tests/api/test_rules.py::test_post_rule_validates_schedule_cron` |
| **R-FA-02** | False alerts | Detection с bbox вне ROI-polygon создаёт alert (point-in-polygon неверен). | Medium | High | TODO: not covered. Покрывается отдельным API-тестом, который не вошёл в текущий scope (4 UI / 13 API / 1 e2e). Идея теста — в `bug_report_examples.md` BUG-002. |
| **R-FA-03** | False alerts | Дубликат `external_id` создаёт второй AlertEvent и повторно запускает action chain. | High | Critical | `tests/api/test_detections.py::test_post_detection_is_idempotent_on_duplicate_external_id` |
| **R-LO-01** | Loss of event | DetectionEvent зафиксирован, но AlertEvent / ArchiveItem не создан (из-за exception в actions_runner). | Medium | Critical | `tests/api/test_archive.py::test_list_archive_returns_200_and_pagination_metadata`, `tests/api/test_archive.py::test_list_archive_filters_by_camera_id`, `tests/ui/test_archive_page.py::test_filter_archive_by_camera_id_updates_url_and_table` |
| **R-AC-01** | Action chain | В `sequential` mode действия выполняются параллельно (порядок не соблюдается). Главная фича Monitoreal v2.4.1. | High | Critical | `tests/e2e/test_multiple_actions_per_rule.py::test_detection_triggers_rule_with_4_sequential_actions_and_creates_archive` (e2e flagship), `tests/api/test_actions.py::test_post_run_action_chain_executes_sequentially`, `tests/api/test_rules.py::test_post_rule_persists_actions_with_order_index`, `tests/ui/test_rules_page.py::test_create_rule_via_modal_appears_in_table` |
| **R-AC-02** | Action chain | Правило без действий принимается / триггерится (action из удалённого правила всё ещё фаерится). | Medium | High | `tests/api/test_rules.py::test_post_rule_rejects_payload_without_actions` (частично — на этапе создания). Триггер удалённого rule — TODO. |
| **R-RET-01** | Retention | `DELETE /api/v1/media/expired` удаляет не-expired ArchiveItem (off-by-one в фильтре). | Low | Critical | `tests/api/test_retention.py::test_delete_expired_removes_only_past_retention_items` |
| **R-RET-02** | Retention | `expires_at` сохраняется как naive datetime, не учитывает таймзону → ошибка на 3 часа на ru-стороне. | Medium | High | `tests/api/test_archive.py::test_list_archive_excludes_already_expired_items` |
| **R-AUTH-01** | Auth | API-key валиден, но роль недостаточна для эндпоинта → возвращается 200 вместо 403. | Medium | Critical | `tests/api/test_retention.py::test_delete_expired_requires_admin_role`, `tests/ui/test_login.py::test_login_with_valid_admin_key_redirects_to_rules`, `tests/ui/test_login.py::test_login_with_invalid_key_shows_error_and_stays_on_login` |
| **R-PRIV-01** | Privacy | Mock-сервер делает реальный исходящий HTTP-запрос (webhook action) в тестовой среде → ложит на чей-то прод. | Low | High | TODO: not covered. Текущая реализация webhook-action в `services/actions_runner.py` — моковая (`asyncio.sleep`), реальный HTTP не отправляется. Защита on-by-design, но нужен тест-страж против регрессии. |

## Контрактные тесты как ортогональное покрытие

13 contract-тестов (`tests/contract/*`) проверяют, что API-ответы соответствуют OpenAPI 3.1 контракту. Они не привязаны к одному риску, но защищают от целого класса проблем: дрейф контракта, нарушение схем, неконсистентные коды ошибок (RFC 7807 Problem Details). Это входной фильтр для всех остальных рисков выше — если контракт сломан, дальше тестировать бесполезно.

## Что не покрыто тестами

- **R-FA-02** (bbox вне ROI) — `_point_in_polygon` реализован, но юнит-теста на edge-cases полигона нет. Логичный следующий шаг — property-based через Hypothesis.
- **R-PRIV-01** — webhook-action сейчас mock (`asyncio.sleep`), реальный HTTP не отправляется. Защита on-by-design, но нет теста-стража против регрессии.
- **R-AC-02** (часть) — триггер действия из уже удалённого правила. Требует двух POST + 1 DELETE, не уместился в текущий scope.

## Связи

- `docs/test_strategy.md` §3 — как риски учтены в стратегии.
- `docs/bug_report_examples.md` — два примера привязаны к R-AC-01 и R-FA-02.
