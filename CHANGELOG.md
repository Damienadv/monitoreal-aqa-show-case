# Changelog

## [0.1.0] — 2026-05-25

Первый публичный релиз.

### Added
- Mock REST API на FastAPI: 11 эндпоинтов с OpenAPI 3.1 контрактом.
- ORM на SQLAlchemy 2.x async + SQLite, 6 моделей, seed двух камер на старте.
- Rules engine с матчингом по object_type / threshold / ROI / cron.
- Actions runner: sequential / parallel для chain из relay, audio, mobile_push, webhook.
- Retention через `DELETE /api/v1/media/expired` (admin-only).
- Demo UI на Jinja2: login, rules, archive.
- 35 тестов: 13 API + 13 contract + 4 UI + 1 e2e flagship.
- GitHub Actions CI (lint + tests + ui-tests + docker smoke) и Allure на Pages.
- Docker Compose + Makefile, `make up && make test-all` поднимает всё.

### Fixed
- OverflowError в пагинации archive/events — добавлен `le=1_000_000` на page/per_page.
