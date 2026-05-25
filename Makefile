.PHONY: help up down logs lint typecheck test-api test-contract test-ui test-e2e \
        test-all report clean dev-local

PYTHON ?= uv run python
PYTEST ?= uv run pytest
ALLURE_RESULTS ?= allure-results

help: ## показать справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## поднять mock-api в Docker
	docker compose up -d --build
	@echo "Ждём health-check..."
	@for i in $$(seq 1 30); do \
		curl -fsS http://localhost:8000/health >/dev/null 2>&1 && echo "✅ /health OK" && exit 0; \
		sleep 1; \
	done; \
	echo "❌ Health-check не прошёл за 30 сек"; exit 1

down: ## остановить и удалить контейнеры + volumes
	docker compose down -v

logs: ## tail логов mock-api
	docker compose logs -f mock-api

dev-local: ## запустить uvicorn без Docker (для разработки и тестов на WSL без Docker)
	uv run uvicorn mock_server.main:app --reload --host 0.0.0.0 --port 8000

lint: ## ruff + mypy
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

typecheck: ## только mypy
	uv run mypy src

test-api: ## API regression тесты
	$(PYTEST) tests/api -v --alluredir=$(ALLURE_RESULTS)

test-contract: ## OpenAPI contract тесты
	$(PYTEST) tests/contract -v --alluredir=$(ALLURE_RESULTS)

test-ui: ## Playwright UI smoke
	$(PYTEST) tests/ui -v --alluredir=$(ALLURE_RESULTS)

test-e2e: ## End-to-end сценарии
	$(PYTEST) tests/e2e -v --alluredir=$(ALLURE_RESULTS)

test-all: lint ## линтер + все 4 слоя тестов
	$(PYTEST) tests -v --alluredir=$(ALLURE_RESULTS)

report: ## показать Allure-отчёт локально (требует allure CLI)
	allure serve $(ALLURE_RESULTS)

clean: ## удалить кеши, отчёты, БД
	rm -rf $(ALLURE_RESULTS) allure-report reports/*.html reports/*.json \
		.pytest_cache .mypy_cache .ruff_cache htmlcov data/*.db
