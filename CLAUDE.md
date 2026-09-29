# CLAUDE.md — Travo project memory (read this first)

**Travo** is an agentic legal-process platform for law firms in Southeast Asia
(Vietnam, Singapore, Indonesia, Malaysia). Wedge product: **contract & agreement
review**. It acts as a "digital senior associate": it runs long legal workflows on
a domain-tuned open-weight model pipeline, grounds every claim in retrieved
legal sources with per-claim citation checks, and escalates hard sub-tasks to
frontier models through a **model-agnostic, conflict-aware router**.

## Current phase
- **Phase:** P0 — foundations in progress. Local-testable slice done (tenancy + RLS,
  ethical walls, encrypted storage, router v0, classify/extract agents, audit, evals).
- **Next step:** remaining P0 items in `docs/12-roadmap.md` §P0 checklist (cloud infra,
  real SSO, Temporal, Langfuse/OTel, real T1 endpoint, 30 real NDAs).
- Before starting work, read `memory/SESSION_LOG.md` (latest entry) and
  `memory/DECISIONS.md`.

## Doc map
| Doc | What it decides |
|---|---|
| `docs/00-competitive-analysis.md` | Harvey vs Legora vs Travo, positioning |
| `docs/01-product-vision-and-prd.md` | Personas, MVP scope, metrics, pricing |
| `docs/02-system-architecture.md` | Components and how they connect |
| `docs/03-model-routing-and-hybrid-inference.md` | Router policy, escalation, conflict-aware providers, BYO keys vs proxy |
| `docs/04-legal-rag-and-citation-validation.md` | Legal corpora, retrieval, per-claim citation validation |
| `docs/05-contract-review-workflow.md` | MVP workflow, agent graph, playbooks |
| `docs/06-security-compliance-ethical-walls.md` | Isolation, ethical walls, ASEAN data-protection law mapping |
| `docs/07-hitl-telemetry-data-flywheel.md` | Expert corrections, telemetry, post-training loop |
| `docs/08-ux-ui-spec.md` | Screens, interaction patterns, self-adaptive loop UX |
| `docs/09-data-model-and-apis.md` | Entities and API surface |
| `docs/10-tech-stack.md` | Chosen stack and why |
| `docs/11-evaluation-and-quality.md` | Evals, release gates |
| `docs/12-roadmap.md` | Phases, milestones, team, risks |
| `docs/13-open-questions.md` | Items needing founder decisions |

## Conventions
- Specs are the source of truth. When implementation diverges, update the spec
  in the same commit.
- Every doc starts with a header block: Status / Last updated / Related.
- Architectural decisions go in `memory/DECISIONS.md` as ADRs (append-only;
  supersede, don't edit history).
- End each working session by appending an entry to `memory/SESSION_LOG.md`
  (date, what changed, what's next, open threads).
- Legal/technical vocabulary: `memory/GLOSSARY.md`.
- Claims about competitors or laws are dated; mark unverified items `[verify]`.
- Never hard-code a model vendor in business logic — everything goes through the
  router (ADR-002).

## Repo layout
Modular monolith in one uv project (ADR-008): packages import each other in-process and
can be split into deployables later.
```
services/api      travo_api    FastAPI app, auth, walls, audit, storage, admin, migrations
services/router   travo_router Task descriptor, policy engine, provider adapters, Router
services/rag      travo_rag    parsing (DOCX/PDF/TXT), language ID, clause segmentation
services/agents   travo_agents taxonomy, classify/extract agents, travo_rules T0 model, pipeline
config/           endpoints.yaml (model catalogue), default_policy.yaml
evals/            gold/nda (synthetic), harness.py, make_gold.py
tests/            pytest; spins up an ephemeral Postgres 16 automatically
scripts/          create_app_role.sql
```
Not yet created (planned): `apps/web`, `apps/word-addin`, `services/flywheel`,
`packages/schemas`, `infra/`.

## Dev commands
```
make install      # uv sync
make check        # ruff + mypy + pytest (tests start their own Postgres)
make eval         # clause/classification scores on gold NDAs
make db-up db-migrate dev   # local API on :8000 (needs Docker + .env from .env.example)
PYTHONPATH=services/api:services/rag:services/router:services/agents \
  uv run python -m travo_api.cli bootstrap-tenant "Firm" admin@firm.test   # then mint-token
```

## Invariants the code relies on
- The API connects as `travo_api` (member of `travo_app`), never as owner/superuser, so RLS
  applies. Every request runs in `tenant_session()` which sets `app.tenant_id`.
- Matter content is reachable only by `matter_members.access = 'member'` — admins included.
  Unauthorised access returns 404 and writes `matter.access_denied` to the audit log.
- `audit_events` and `routing_decisions` are append-only (trigger + grants).
- Endpoint `provider` = model vendor; `via` = aggregator/host. Deny/allow lists and matter
  conflicts apply to both. `travo` (first party) is exempt from allowlists only.
