PY_PATH := services/api:services/rag:services/router:services/agents:.
export PYTHONPATH := $(PY_PATH)

.PHONY: install lint fmt typecheck test eval db-up db-migrate dev check worker ingest-legal \
	web-install web-dev web-check e2e dev-token mock-idp legal-fetch legal-verify

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

# Fetch + parse official statutes (docs/runbooks/legal-ingestion.md). JUR=SG|MY, OFFLINE=1.
legal-fetch:
	uv run python -m travo_api.cli legal-fetch $(if $(JUR),-j $(JUR)) $(if $(OFFLINE),--offline)

# Record a lawyer's check: make legal-verify SOURCE=SG/UCTA1977 BY=lawyer@firm.sg
legal-verify:
	uv run python -m travo_api.cli legal-verify $(SOURCE) --by $(BY)

web-install:
	cd apps/web && pnpm install --frozen-lockfile

web-dev:
	cd apps/web && TRAVO_DEV_LOGIN=true TRAVO_API_URL=$${TRAVO_API_URL:-http://localhost:8000} pnpm dev

web-check:
	cd apps/web && pnpm typecheck && pnpm lint && pnpm test

e2e:
	scripts/e2e.sh

# Dev sign-in token for the web app (creates a demo tenant + partner on first use).
dev-token:
	@uv run python -m travo_api.cli dev-token

# Test-only OIDC provider for local SSO: users via MOCK_USERS="a@firm.test b@firm.test"
mock-idp:
	uv run python -m scripts.mock_oidc --port 8791 --client-id travo-web $(foreach u,$(MOCK_USERS),--user $(u))
