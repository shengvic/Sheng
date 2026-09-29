PY_PATH := services/api:services/rag:services/router:services/agents:.
export PYTHONPATH := $(PY_PATH)

.PHONY: install lint fmt typecheck test eval db-up db-migrate dev check

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
