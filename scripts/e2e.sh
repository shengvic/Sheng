#!/usr/bin/env bash
# End-to-end: ephemeral Postgres → migrations → fixture legal corpus → API (inline reviews)
# → next dev → Playwright. Usage: scripts/e2e.sh [playwright args]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PGB="${TRAVO_PG_BIN:-/usr/lib/postgresql/16/bin}"
PG_PORT="${E2E_PG_PORT:-55440}"
API_PORT="${E2E_API_PORT:-8790}"
WEB_PORT="${E2E_WEB_PORT:-3790}"
WORK="$(mktemp -d /tmp/travo-e2e-XXXX)"
as_pg() { if [ "$(id -u)" = 0 ]; then runuser -u postgres -- "$@"; else "$@"; fi; }
cleanup() {
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  if [ -z "${TRAVO_TEST_ADMIN_DATABASE_URL:-}" ]; then
    as_pg "$PGB/pg_ctl" -D "$WORK/data" -m fast stop >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

if [ -n "${TRAVO_TEST_ADMIN_DATABASE_URL:-}" ]; then   # CI: Postgres service container
  ADMIN_BASE="${TRAVO_TEST_ADMIN_DATABASE_URL%/*}"
  HOSTPART="${ADMIN_BASE#*@}"
else
  [ "$(id -u)" = 0 ] && chown postgres "$WORK"
  chmod 755 "$WORK"
  as_pg "$PGB/initdb" -D "$WORK/data" -U postgres -A trust -E UTF8 --no-instructions >/dev/null
  as_pg "$PGB/pg_ctl" -D "$WORK/data" -l "$WORK/pg.log" -w \
    -o "-p $PG_PORT -k $WORK -h 127.0.0.1" start >/dev/null
  ADMIN_BASE="postgresql+psycopg://postgres@127.0.0.1:$PG_PORT"
  HOSTPART="127.0.0.1:$PG_PORT"
fi
DB="travo_e2e_$$"
PSQL_URL="${ADMIN_BASE/postgresql+psycopg/postgresql}"
psql "$PSQL_URL/postgres" -qc "CREATE DATABASE $DB"

export TRAVO_ADMIN_DATABASE_URL="$ADMIN_BASE/$DB"
export TRAVO_DATABASE_URL="postgresql+psycopg://travo_api:travo_api@$HOSTPART/$DB"
export TRAVO_MASTER_KEY="$(python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')"
export TRAVO_JWT_SECRET="e2e-$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
export TRAVO_STORAGE_DIR="$WORK/objects"
export TRAVO_INLINE_REVIEWS=true
export PYTHONPATH="services/api:services/rag:services/router:services/agents:."
CLI="uv run python -m travo_api.cli"

uv run alembic -c services/api/alembic.ini upgrade head >/dev/null
psql "$PSQL_URL/$DB" -q -f scripts/create_app_role.sql
$CLI ingest-legal tests/fixtures/legal_fixture.jsonl >/dev/null
OUT="$($CLI bootstrap-tenant "Lion & Partners LLP" admin@lionpartners.test)"
TID="$(echo "$OUT" | sed -n 's/tenant_id=//p')"
PARTNER="$($CLI add-user "$TID" wei.ling@lionpartners.test partner)"
export E2E_TOKEN="$($CLI mint-token "$TID" "$PARTNER" --ttl 7200)"

uv run uvicorn travo_api.main:app --port "$API_PORT" >"$WORK/api.log" 2>&1 &
API_PID=$!
(cd apps/web && TRAVO_API_URL="http://127.0.0.1:$API_PORT" NEXT_TELEMETRY_DISABLED=1 \
  pnpm exec next dev -p "$WEB_PORT" >"$WORK/web.log" 2>&1) &
WEB_PID=$!
for _ in $(seq 120); do
  curl -sf "http://127.0.0.1:$API_PORT/healthz" >/dev/null && curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/login" && break
  sleep 1
done

export E2E_BASE_URL="http://localhost:$WEB_PORT"  # Next dev blocks dev assets for 127.0.0.1
export E2E_FIXTURES="$ROOT/evals/gold/nda"
status=0
(cd apps/web && pnpm exec playwright test "$@") || status=$?
if [ "$status" != 0 ]; then
  echo "---- api.log (tail) ----"; tail -40 "$WORK/api.log"
  echo "---- web.log (tail) ----"; tail -40 "$WORK/web.log"
fi
exit "$status"
