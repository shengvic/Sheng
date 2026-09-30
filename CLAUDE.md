# CLAUDE.md — Travo project memory (read this first)

**Travo** is an agentic legal-process platform for law firms in Southeast Asia
(Vietnam, Singapore, Indonesia, Malaysia). Wedge product: **contract & agreement
review**. It acts as a "digital senior associate": it runs long legal workflows on
a domain-tuned open-weight model pipeline, grounds every claim in retrieved
legal sources with per-claim citation checks, and escalates hard sub-tasks to
frontier models through a **model-agnostic, conflict-aware router**.

## Current phase
- **Phase:** P1 — slices 1 (review engine), 2 (review canvas), 3 (SSO sign-in + admin
  console), 4 (official-statute pipeline + lawyer verification) and 5 (parser hardened on real
  AGC reprints; MY Contracts Act + PDPA parsed, unverified) done. P0 infra still open.
- **Launch market: Vietnam first (ADR-021).** Plan and workstreams V0–V9 in
  `docs/14-vietnam-launch-plan.md`; SG/MY stay built but follow VN. MVP pilot (ADR-022): Coolify
  on a Contabo VPS, hosted open-weight model APIs, legal texts scraped from official VN sites,
  scope NDA / commercial contracts / services / DPA.
- **VN pilot release-ready (2026-09-30, docs/14 §13, ADR-023):** bilingual contracts (clause
  pairs, `bilingual` findings), draft VN playbooks + pack, VN statute parser, unaccented search,
  offshore switch, output language, Vietnamese UI, sign-in rate limit, VN gold gates.
- **Next step:** deploy to the Coolify VPS (waits on SSH access + domain), then `legal-fetch -j VN`
  on the VPS → ingest → lawyer `legal-verify`; lawyer sign-off of the VN playbooks; DPA and
  transfer dossier before real client documents. VN legal domains are blocked in the dev
  environment's network policy.
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
| `docs/14-vietnam-launch-plan.md` | Vietnam-first launch: scope, corpus, bilingual review, residency, workstreams |

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
                               citations (per-claim validator), sources/ (manifest, polite
                               fetch + snapshots, HTML/PDF parsers, review report)
services/agents   travo_agents taxonomy, classify/extract/compare/lawcheck/redline/memo agents,
                               playbooks + checks, prompts/<task>/v1.md, travo_rules T0 model
config/           endpoints.yaml, default_policy{,_vn}.yaml, review.yaml, playbooks/*.yaml
                  (*_vn drafts), jurisdiction_packs/*.yaml, legal_sources/{sg,my,vn}.yaml
evals/            gold/nda (synthetic), harness.py (+ VN gates), make_gold.py, vn_fixtures.py
                  (bilingual DOCX builders), vn_gold.py (VN pilot set, 4 contract types)
tests/            pytest; ephemeral Postgres 16; fixtures/legal_fixture.jsonl (NOT real law)
scripts/          create_app_role.sql, e2e.sh (Postgres + mock IdP + API + next dev + Playwright),
                  mock_oidc.py (test-only OIDC provider), deploy_smoke.py (compose stack smoke test)
deploy/           Dockerfile.api (api + worker), Dockerfile.web, docker-compose.coolify.yml,
                  smoke.override.yml (TEST ONLY), backup.sh, .env.example — ADR-022
apps/web          Next.js 16: src/app (pages; auth/* + api/[...path] BFF route handlers; admin),
                  src/proxy.ts (CSP nonce, login redirect), src/components, src/lib (api client,
                  types mirroring schemas.py, csrf/pkce/csp + vitest), e2e/
```
Not yet created (planned): `apps/word-addin`, `services/flywheel`, `packages/schemas`, `infra/`.

## Dev commands
```
make install      # uv sync
make check        # ruff + mypy + pytest (tests start their own Postgres)
make eval         # clause/classification scores on gold NDAs
make db-up db-migrate dev   # local API on :8000 (needs Docker + .env from .env.example)
make worker       # process queued review runs (or TRAVO_INLINE_REVIEWS=true for dev)
make ingest-legal FILE=units.jsonl   # load legal units into the shared index (owner conn)
make legal-fetch JUR=SG [OFFLINE=1]  # fetch + parse statutes → out/legal/SG.jsonl + review report
make legal-import FILE=act.pdf ID=MY/ACT136 [URL=https://…]  # store a hand-downloaded file
make legal-verify SOURCE=SG/UCTA1977 BY=lawyer@firm.sg   # record a lawyer's check
TRAVO_REAL_LEGAL_DIR=.data/real_legal uv run pytest tests/test_legal_real_pdfs.py  # real reprints
make web-install web-check           # pnpm install; tsc + eslint + vitest
make dev-token                       # demo tenant + partner token (dev sign-in form)
make web-dev                         # Next on :3000 with TRAVO_DEV_LOGIN=true; BFF → TRAVO_API_URL
make mock-idp                        # local OIDC provider on :8791 (then `cli configure-idp`)
make e2e                             # full browser flow (needs Postgres binaries + Chromium)
make deploy-smoke                    # build images + run the Coolify compose stack with a mock IdP
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
- Real statutes enter only via `legal-fetch` → `ingest-legal` (raw snapshots + sha256). New or
  changed snapshots are `unverified`; `TRAVO_REQUIRE_VERIFIED_SOURCES=true` in pilots/prod (ADR-019).
  Real statute files (PDFs/snapshots) never go in git; the parser must never drop body text
  silently — keep its accounting check at zero (ADR-020).
- Few-shot examples are filtered to matters the initiator is a member of (ADR-015).
- Bilingual contracts: clauses hold the primary language in `text`, the other in `text_alt`;
  checks read `text`. VI–EN differences are `kind = bilingual` findings (ADR-023). Output language
  lives in `review_runs.options`; T0 messages have en/vi variants — add both.
- Web: `apps/web/src/lib/types.ts` mirrors `schemas.py` — change both together. UI strings live in
  `src/i18n/{en,vi}.ts` (same `Dict` shape) and are read via `useT()`; no hard-coded labels. The browser only
  calls `/api/*` and `/auth/*` (same origin) and never holds a bearer token: it lives in the
  httpOnly `travo_session` cookie. Writes need the `X-Travo-CSRF: 1` header. Use `localhost`, not
  `127.0.0.1`, for `next dev`. Next 16 calls middleware `proxy.ts`.
- Deploy: `TRAVO_ENV=production` makes unsafe settings a startup failure (`production_problems()`)
  and requires https identity providers. Only `web` is public; `api` runs `travo migrate` on start
  (creates the app role from `TRAVO_DATABASE_URL`). Runbook: `docs/runbooks/deploy-coolify.md`.
- Sign-in: the API maps IdP identities to existing users only (no JIT); cross-firm lookups only
  via `idp_for_email_domain()` / `idp_by_id()`. `TRAVO_ALLOW_DEV_TOKENS` must be false in any
  deployment with client data (ADR-018).
