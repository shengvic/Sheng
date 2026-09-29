# CLAUDE.md — Travo project memory (read this first)

**Travo** is an agentic legal-process platform for law firms in Southeast Asia
(Vietnam, Singapore, Indonesia, Malaysia). Wedge product: **contract & agreement
review**. It acts as a "digital senior associate": it runs long legal workflows on
a domain-tuned open-weight model pipeline, grounds every claim in retrieved
legal sources with per-claim citation checks, and escalates hard sub-tasks to
frontier models through a **model-agnostic, conflict-aware router**.

## Current phase
- **Phase:** P1 — slice 1 (backend review engine) done: durable review runs, playbooks,
  compare/law-check/redline/memo agents, legal index + citation validator, escalation,
  dispositions, export gate, DOCX exports. P0 infra items still open.
- **Next step:** P1 slice 2 = review canvas web UI; then real legal corpus ingestion. See
  `docs/12-roadmap.md` §P1 checklist.
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
services/api      travo_api    FastAPI app, auth, walls, audit, storage, admin, migrations,
                               workflows.py (durable runner), reviews.py (steps), exports.py
services/router   travo_router Task descriptor, policy engine, provider adapters, Router
services/rag      travo_rag    parsing, language ID, segmentation, legal_index, retrieval,
                               citations (per-claim validator)
services/agents   travo_agents taxonomy, classify/extract/compare/lawcheck/redline/memo agents,
                               playbooks + checks, prompts/<task>/v1.md, travo_rules T0 model
config/           endpoints.yaml, default_policy.yaml, review.yaml, playbooks/*.yaml,
                  jurisdiction_packs/*.yaml
evals/            gold/nda (synthetic), harness.py, make_gold.py
tests/            pytest; ephemeral Postgres 16; fixtures/legal_fixture.jsonl (NOT real law)
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
make worker       # process queued review runs (or TRAVO_INLINE_REVIEWS=true for dev)
make ingest-legal FILE=units.jsonl   # load legal units into the shared index (owner conn)
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
- Review workers touch other tenants only through `claim_review_run()` (returns ids); step work
  runs in `tenant_session()`. A step writes its rows and its `completed` marker in one
  transaction — keep steps idempotent under retry.
- `telemetry_events` is append-only too. Legal text only enters via `ingest-legal`; never write
  statute text by hand (ADR-014). Fixture units are titled "FIXTURE — not law".
- Few-shot examples are filtered to matters the initiator is a member of (ADR-015).
