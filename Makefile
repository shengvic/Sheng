PY_PATH := services/api:services/rag:services/router:services/agents:.
export PYTHONPATH := $(PY_PATH)

.PHONY: install lint fmt typecheck test eval db-up db-migrate dev check worker ingest-legal \
	web-install web-dev web-check e2e dev-token

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

test:
	uv run pytest -q

eval:
	uv run python -m evals.harness

check: lint typecheck test

db-up:
	docker compose up -d --wait postgres

db-migrate:
	uv run alembic -c services/api/alembic.ini upgrade head
	docker compose exec -T postgres psql -U postgres -d travo < scripts/create_app_role.sql

dev:
	uv run uvicorn travo_api.main:app --reload --port 8000

worker:
	uv run python -m travo_api.cli worker

ingest-legal:
	uv run python -m travo_api.cli ingest-legal $(FILE)

web-install:
	cd apps/web && pnpm install --frozen-lockfile

web-dev:
	cd apps/web && TRAVO_API_URL=$${TRAVO_API_URL:-http://localhost:8000} pnpm dev

web-check:
	cd apps/web && pnpm typecheck && pnpm lint && pnpm test

e2e:
	scripts/e2e.sh

# Dev sign-in token for the web app (creates a demo tenant + partner on first use).
dev-token:
	@uv run python -m travo_api.cli dev-token
