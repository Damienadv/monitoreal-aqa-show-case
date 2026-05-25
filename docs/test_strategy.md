# Test strategy

Что тестируем, как приоритизируем, где граница ручного/автоматического и что блокирует merge. Стек инструментов — в `pyproject.toml`.

---

## 1. Цель тестирования

Доказать, что mock-сервис ведёт себя как **спецификация**, описанная в `docs/api_contract.yaml`, при следующих гарантиях:

- На детекцию с подходящими признаками гарантированно срабатывает правило и порождается AlertEvent + ArchiveItem.
- На детекцию с дубликатом `external_id` повторного срабатывания не происходит.
- Action chain в `sequential` mode сохраняет порядок `order_index`.
- ArchiveItem уважает retention и не возвращается после `expires_at`.
- API роли разграничены: viewer не пишет, camera не админит, admin не отвечает за UI.

Тестирование считаем «успешно завершённым», если все эти инварианты проверены на каждый коммит в `main` через CI и красная зона воспроизводится локально командой `make test-all`.

## 2. Объекты тестирования

**В scope:**
- REST API на FastAPI (`/api/v1/*`) — 11 эндпоинтов, описанных OpenAPI 3.1.
- Demo UI на Jinja2 (`/`, `/rules`, `/archive`) — три страницы, минимум для интерактивной демо-проверки domain flow.
- Конформность ответов API контракту OpenAPI (contract testing).
- End-to-end сценарий «multiple actions per rule», отсылка к Monitoreal v2.4.1.

**Вне scope (явный «Won't»):**
- Mobile (Appium, BrowserStack) — не входит в bounded showcase.
- Реальные RTSP / IP-камеры — мокаем DetectionEvent через HTTP.
- Прошивка / firmware — выходит за пределы Python-стека.
- Нагрузка (k6, Locust) — нет смысла нагружать mock; для прод-нагрузки нужен профайлинг реального сервиса.
- Безопасность как пентест — есть отдельный аудит зависимостей, но не fuzz-тестирование сетевого стека.
- Микросервисная архитектура — mock монолитен по дизайну (SQLite + FastAPI достаточно для showcase'а).

## 3. Риски продукта

Полная матрица: `docs/risk_matrix.md`. Кратко: 10 рисков в 6 категориях (false alerts, loss of event, action chain, retention, auth, privacy). 8 из 10 закрыты тестами, 2 (R-FA-02 ROI и R-PRIV-01 outbound HTTP) явно помечены `TODO: not covered` с обоснованием в матрице.

Главные риски с Impact=Critical: R-FA-01 (false alert from low confidence), R-FA-03 (duplicate detection), R-LO-01 (потеря события), R-AC-01 (нарушение sequential mode), R-RET-01 (off-by-one в retention DELETE), R-AUTH-01 (insufficient role → 200). Все закрыты минимум одним тестом, R-AC-01 — целым стеком: e2e + 2 API + 1 UI.

## 4. Уровни тестирования

Четыре слоя, по нарастанию стоимости и убыванию количества:

| Слой | Цель | Количество | Время одного |
|---|---|---|---|
| API | Регресс инвариантов бизнес-логики через REST. | 13 | ~50 ms |
| Contract | Соответствие ответов OpenAPI 3.1 контракту (Schemathesis property-based + inline jsonschema). | 13 | ~200 ms |
| UI | Smoke на критичных user flows: login, rules CRUD, archive filter. | 4 | ~1 s |
| E2E | Один флагман: «detection → правило с 4 actions → sequential выполнение → archive». | 1 | ~400 ms |

Пирамида намеренно сужена: e2e — 1 тест, UI — 4. Это **бюджет**, не «как сложилось». Дополнительные UI-тесты добавляются только если открывается новый риск, которого нет в матрице.

## 5. Что автоматизируем в первую очередь и почему

Приоритет: **API > contract > e2e > UI**.

- **API** идёт первым, потому что (1) дешёвый, (2) ловит ⅔ всех багов до того, как они дойдут до UI, (3) выполняется на каждом коммите за секунды. ROI самый высокий.
- **Contract** идёт вторым, потому что один сломанный контракт обесценивает все API-тесты ниже («тестируем не то, что обещали»). Schemathesis генерирует hypothesis-кейсы автоматически — низкая стоимость поддержки.
- **E2E** идёт третьим: один тест, дорогой в поддержке, но **показывает рецензенту**, что соискатель читал release notes (v2.4.1 Multiple Actions per Rule). Один тест умещается в скриншот, что важно для cover letter.
- **UI** идёт последним, потому что хрупкий, медленный и закрывает только smoke. 4 теста — это минимум, чтобы продемонстрировать навык работы с Playwright, не больше.

Manual exploratory упомянут в §6 ниже; он не оплачивается ресурсами CI, поэтому в приоритизации автоматизации не учитывается.

## 6. Что проверяем вручную

- **UX оценка demo UI.** Один проход глазами после каждой UI-фичи: верстка не разъезжается на 1280×720 и 360×640, контраст текста читабелен на dark theme.
- **Exploratory на mobile-сценарии.** Mobile push action в коде — mock; ручной чек, что payload в `actions_executed` содержит ожидаемые поля.
- **Демо-сценарий перед демо рецензенту.** `make up` → открыть `/rules` → создать правило с 3 actions → POST detection через curl → проверить, что AlertEvent виден в `/archive`. Это и есть «дымовой запуск» перед отправкой ссылки.
- **Security review зависимостей.** `uv pip list --outdated` + `pip-audit` локально (не в CI, чтобы не блокировать merge).

Эти ручные проверки **не дублируются автотестами**: либо они про UX, который алгоритмически не валидируется, либо про действия раз в неделю.

## 7. Регресс-пайплайн

CI (`.github/workflows/ci.yml`) — 4 параллельные джобы после `lint`:

```
lint ─┬─► tests       (api + contract + e2e)  ──► allure-results-api artifact
      ├─► ui-tests    (Playwright chromium)   ──► allure-results-ui artifact
      └─► docker-build (build image + smoke /health)
```

Allure Pages workflow (`.github/workflows/allure-pages.yml`) триггерится **после** успешного CI:
- Скачивает оба `allure-results-*` артефакта.
- Мерджит, генерирует отчёт с историей последних 20 запусков.
- Деплоит на `gh-pages` через `actions/deploy-pages`.

Разделение «smoke vs full»:
- **Smoke** = lint + `tests/api/test_detections.py` + docker `/health`. Запускается на every push.
- **Full** = все 4 джобы. Тоже на every push, потому что общий runtime ≤ 4 минут (NFR в PRD §7).

PR merge заблокирован, если красный любой из: lint, tests, ui-tests, docker-build. Mypy сейчас в `continue-on-error: true` — есть 2 pre-existing warning, которые не блокируют, но видны в логах.

## 8. Test data strategy

**Изоляция БД.** Каждый тест получает свежую in-memory SQLite через фикстуру `db_engine` в `tests/conftest.py`: при старте создаётся новый engine, схема накатывается заново, seed-данные (cam-01, cam-02) добавляются, после теста engine dispose'ится. **Никакого shared state между тестами.**

**Фабрики.** В `tests/factories.py` — нативные async-функции (без `factory_boy`), осознанный выбор простоты над DSL-ем. Главные:
- `make_rule(session, ...)` — правило с настраиваемым action_mode и списком actions.
- `detection_payload(...)` — JSON-словарь для POST /api/v1/detections.
- `make_archive_item(...)` / `make_alert_with_archive(...)` — для тестов архива и retention.

Принципы:
- **Defaults осмысленные:** `confidence=0.95`, `object_type="person"`, `external_id="evt-001"` — этого достаточно для happy path.
- **Override через kwargs:** каждый тест переопределяет только то, что важно для проверяемого инварианта.
- **Никаких хитрых side-effects:** фабрика возвращает persisted объект и больше ничего не делает.

UI-тесты используют отдельный fixture `ui_server_url` (session-scoped uvicorn subprocess) с временной SQLite-файловой базой — потому что Playwright нужен реальный HTTP-сервер.

## 9. CI/CD quality gates

**Блокируют merge:**
1. `ruff check .` — 0 ошибок.
2. `ruff format --check .` — все файлы отформатированы.
3. `pytest tests/api tests/contract tests/e2e` — 100% зелёных.
4. `pytest tests/ui` — 100% зелёных на headless chromium.
5. `docker build` + smoke `/health` — образ собирается и поднимается за 10 секунд.

**Не блокируют (информационные):**
- `mypy src` — есть 2 pre-existing warning в conftest и контракт-тесте, не блокируют, но видны в логах. Cleanup запланирован в follow-up.
- Allure report — публикация на Pages идёт после CI; падение публикации не означает падение тестов.

**Что НЕ проверяется в CI и почему:**
- Coverage % — намеренно. Coverage без привязки к рискам — карго-культ; вместо этого матрица в `risk_matrix.md` объясняет, ЧТО покрыто и ЧТО нет.
- Mutation testing — слишком дорого для бюджета шоукейса; в реальном проекте добавил бы `mutmut` на критичные модули (rules_engine).
- License check — поднимается локально через `pip-licenses`, но в CI ради скорости пропущен.

## 10. Observability

**В коде:**
- Логи `uvicorn` идут в stdout (без structured JSON — упрощение для mock'а).
- FastAPI exception handlers нормализуют все ошибки в RFC 7807 Problem Details (`application/problem+json`) — единая точка для grep'а в проде.
- `lifespan` логирует seed cam-01/cam-02 при старте — sanity, что БД доступна.

**В тестах:**
- Allure annotations через `pytest-allure` — каждый тест видно в trends по запускам.
- `pytest-html` self-contained report — `pytest-report.html` загружается в artifacts при каждом CI-run, удобно открыть локально без интернета.

**Что добавил бы в прод-варианте:** трассировка через trace_id в middleware и алерт «detection rate упал ниже X за 5 минут». Остальное — по обстоятельствам.

---

## Связи

- `docs/risk_matrix.md` — детальные риски и mapping на тесты.
- `.github/workflows/ci.yml`, `.github/workflows/allure-pages.yml` — практическая реализация §7 и §9.
