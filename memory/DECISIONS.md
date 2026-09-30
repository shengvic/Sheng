# Architecture & Product Decision Log (ADR)

Append-only. To change a decision, add a new ADR that supersedes the old one.
Format: `ADR-NNN — Title` · Date · Status · Context · Decision · Consequences.

---

## ADR-001 — Docs-first bootstrap
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** Empty repo; need shared understanding before code, and memory for future sessions.
- **Decision:** Write specs in `docs/`, memory in `CLAUDE.md` + `memory/`, before any application code.
- **Consequences:** Specs are the source of truth; code changes must update specs.

## ADR-002 — Model-agnostic, policy-driven router
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** Law firms face provider conflict risk and vendor lock-in; cost requires open-weight models.
- **Decision:** All model calls go through `services/router` with a deterministic policy engine (tenant/client/matter rules, residency, budgets). Vendor SDKs may not be imported elsewhere.
- **Consequences:** Small latency overhead; strong neutrality story; easy provider swaps. See docs/03.

## ADR-003 — Contract & agreement review is the wedge
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** High volume, measurable, playbook-driven, lower risk than litigation advice.
- **Decision:** MVP = contract review with playbooks for SG/MY; research/drafting later.
- **Consequences:** Clause taxonomy and playbook schema are core assets. See docs/05.

## ADR-004 — Hybrid tiers: open-weight T1 default, frontier T2 on escalation
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Long, token-heavy tasks run on T1 (open-weight, post-trained, per-firm LoRA); T2 frontier only via escalation triggers or policy. Early hosting on Fireworks/Baseten, later self-hosted vLLM.
- **Consequences:** Needs calibrated confidence + validator; enables margin and on-prem story. See docs/03.

## ADR-005 — Per-claim citation validation with export gate
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Every legal claim is extracted, checked for existence/validity/pinpoint/entailment; unsupported claims block export unless overridden with an audited reason.
- **Consequences:** Extra latency/cost per review; core trust differentiator. See docs/04.

## ADR-006 — Matter is the security boundary; region cells for residency
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** tenant_id + matter_id on all data; ACLs enforced in API, retrieval, router, telemetry; identical stacks per region cell (SG first, VN/ID later).
- **Consequences:** More infra per region; clean residency answers. See docs/06.

## ADR-007 — Firm-private learning by default, global opt-in only
- **Date:** 2026-09-29 · **Status:** Proposed (confirm with design partners — Q8)
- **Decision:** Corrections train firm-private adapters; contribution to Travo global model is explicit opt-in.
- **Consequences:** Slower global model improvement; much easier adoption. See docs/07.

## ADR-008 — Modular monolith for P0
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** Small team, P0 speed; architecture (docs/02) has many services.
- **Decision:** One uv project; `travo_api`, `travo_router`, `travo_rag`, `travo_agents` are packages with narrow interfaces (`RouterContext`, `Provider`, `Kms`, `ObjectStore`), imported in-process.
- **Consequences:** One deployable now; split later without changing interfaces.

## ADR-009 — Own OpenAI-compatible adapter before LiteLLM
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Router calls endpoints through a small httpx adapter speaking the OpenAI chat-completions format (Fireworks, Baseten, OpenRouter, vLLM, and vendor compatibility endpoints). LiteLLM can be added behind the `Provider` interface later.
- **Consequences:** Less dependency surface; we own retries/cost logic.

## ADR-010 — Conflicts apply to vendor and host; first party exempt from allowlists
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Endpoints carry `provider` (model vendor) and `via` (host/aggregator). Deny lists and matter conflict profiles match either. `travo` passes allowlists but can be denied explicitly. Conflict/vendor reasons are reported before availability reasons in routing logs.
- **Consequences:** Blocking a lab also blocks it through aggregators; audits show the policy reason.

## ADR-011 — Ethical walls bind admins; denials are 404 and audited
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Matter content requires `member` access for every role, including admins; screened or non-member access returns 404 (does not reveal existence) and writes `matter.access_denied` in a separate transaction.
- **Consequences:** Admins manage policy and audit, not client content. Break-glass access is a future, audited feature.

## ADR-012 — Escalation never falls back downward
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** When a task is escalated, endpoints below the escalation tier are excluded (`below_escalation_tier`); otherwise fallback goes preferred tier → lower tiers → higher tiers allowed by the rule.
- **Consequences:** Escalations fail loudly (to human review) rather than silently reusing a weaker model.

## ADR-013 — Postgres-backed durable review runs (Temporal deferred)
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** Reviews are multi-step and must survive crashes; Temporal needs infra not available in dev/CI yet.
- **Decision:** `review_runs` + `review_steps`; each step commits its outputs and `completed` marker atomically; resume skips completed steps; retries with backoff up to `max_attempts`; leases with row locks. Workers claim runs across tenants only via `claim_review_run()` — a `SECURITY DEFINER` function owned by `travo_claimer` (NOLOGIN, BYPASSRLS, rights on `review_runs` only) that returns ids; all work then runs in a tenant-scoped session under RLS. Dev/tests can run reviews inline via an after-commit hook (`TRAVO_INLINE_REVIEWS`).
- **Consequences:** No new infra. Creating a BYPASSRLS role needs a superuser migration role — check managed Postgres support `[verify]`. Swap to Temporal behind `WorkflowRunner` later.

## ADR-014 — Shared legal index; fixtures only until real ingestion
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Public law lives in shared `legal_sources`/`legal_units` (read-only to the app, no tenant data). Test fixtures are titled "FIXTURE — not law". Statute text is never transcribed from memory; real SG/MY units come from official portals via the JSONL ingestion CLI.
- **Consequences:** Law checks in any deployment without an ingested corpus produce `no_sources` → human review, never invented law.

## ADR-015 — Few-shot memory respects ethical walls
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Redline few-shot examples come only from accepted/edited findings in matters where the run's initiator is a `member`. Firm-wide precedent sharing will require explicit KM publication (clause bank), not implicit reuse.
- **Consequences:** Learning is slower across teams but cannot leak walled wording.

## ADR-016 — Export gate semantics
- **Date:** 2026-09-29 · **Status:** Accepted
- **Decision:** Export requires a completed run, every non-`info` finding dispositioned (defer blocks), and every citation on a non-rejected finding `supported` or overridden with a reason by a partner/KM/admin. `info` (standard) findings never block.
- **Consequences:** Lawyers can clear low-value checks quickly while unsupported law cannot reach a client document silently.

## ADR-017 — Web app: client-side data, same-origin proxy, dev-token sign-in until OIDC
- **Date:** 2026-09-29 · **Status:** Accepted (temporary auth)
- **Context:** The review canvas is highly interactive; the API already enforces tenancy, walls and roles. Real SSO (OIDC) is still an open P0 item.
- **Decision:** `apps/web` fetches client-side via TanStack Query; Next.js rewrites `/api/*` to the API so the browser never talks cross-origin (no CORS surface). Sign-in is a dev JWT pasted into `/login` and kept in `sessionStorage`; any 401 clears it. `agentRules: false` stops Next from writing AGENTS.md/CLAUDE.md into the app.
- **Consequences:** Tokens in `sessionStorage` are readable by page scripts — acceptable for dev only. Before pilots: OIDC auth-code + PKCE with an httpOnly session cookie set by the Next server, and CSP headers.

## ADR-018 — Per-firm OIDC sign-in, server-side sessions, BFF cookie (supersedes ADR-017's auth)
- **Date:** 2026-09-29 · **Status:** Accepted
- **Context:** ADR-017's pasted dev token in `sessionStorage` is unacceptable for client data. Each firm has its own IdP (Entra ID, Google, Okta).
- **Decision:** Per-firm OIDC config (`tenant_idps`, one firm per email domain via `idp_domains` PK). Auth code + PKCE; the API performs discovery, code exchange (client secret encrypted with the firm DEK) and id_token validation, maps to an existing user (bind `idp_subject` on first login, no JIT), and issues a session token backed by a revocable `auth_sessions` row. The Next.js BFF keeps it in an httpOnly cookie and adds it server-side on `/api/*`; CSRF header + Origin check on writes; per-request nonce CSP via `proxy.ts`. Sign-in lookups across firms only through two SECURITY DEFINER functions (role `travo_idp_lookup`). Dev tokens remain for local work, gated by `TRAVO_ALLOW_DEV_TOKENS` (must be false in deployments) and the web `TRAVO_DEV_LOGIN` flag.
- **Consequences:** The browser never sees a bearer token; sessions can be revoked centrally. Every API call does one extra session lookup. Still open: SCIM, domain verification, sign-in rate limiting, IdP-initiated logout.

## ADR-019 — Official-source snapshots, provenance and a lawyer verification gate
- **Date:** 2026-09-30 · **Status:** Accepted
- **Context:** Law checks need real SG/MY statutes. ADR-014 forbids hand-written statute text. The portals cannot be reached from the dev environment, and parsed text can be wrong even when it is fetched correctly.
- **Decision:**
  - Statutes enter only through a manifest-driven pipeline (`travo_rag.sources`):
    - a polite fetcher (robots.txt, rate limit, retries, size cap, contact User-Agent);
    - immutable raw snapshots with sha256 metadata, kept out of git;
    - parsers with guards (title check, minimum sections);
    - JSONL plus a Markdown review report, then `ingest-legal`.
  - `legal_sources` records `snapshot_sha256`, `retrieved_at` and `review_status`. New or changed snapshots are `unverified`. A lawyer marks a source `verified` with `legal-verify`.
  - `TRAVO_REQUIRE_VERIFIED_SOURCES=true` (mandatory for pilots and production) limits retrieval to verified sources. The UI labels unverified sources.
- **Consequences:**
  - Real text needs a lawyer's sign-off before it can support a claim; until then findings go to human review.
  - HTML chrome changes force re-verification.
  - Manifest URLs and portal layouts are `[verify]`, and MY PDF URLs must be filled in.
  - Terms of use are open (Q11).

## ADR-020 — Terms of use confirmed; supplied official files; contents-driven statute parser
- **Date:** 2026-09-30 · **Status:** Accepted
- **Context:**
  - The founder confirmed Q11: statute text from the official portals may be stored and served in-product.
  - The first real AGC reprints (supplied as PDFs) showed that the ADR-019 parser silently dropped wrapped lines, parsed contents entries as sections, and missed Malay layouts.
  - The reprints carry a Percetakan Nasional Malaysia Berhad "all rights reserved" notice.
- **Decision:**
  - `legal-import` stores a file someone obtained from the official portal as a snapshot (`origin: supplied`, optional https URL). It then follows the same parse → review → ingest → `legal-verify` path.
  - Raw files never go in git. Tests against real reprints run only when `TRAVO_REAL_LEGAL_DIR` is set, and they derive every expectation from the PDF itself.
  - The splitter is contents-driven and page-aware:
    - Numbered lines start sections only in contents order.
    - Headings and Part lines are matched to the contents table (≥ 0.9 for typos, reported).
    - Chrome is removed only at page edges.
    - `*NOTE` footnotes are set aside.
    - An accounting check guarantees no body text is dropped silently.
  - The UI attributes the issuing body.
- **Consequences:**
  - Schedules and appendices are not ingested yet (reported).
  - Stale reprints (e.g. Contracts Act 2006, PDPA 2023, which predates the 2024 amendments) must be replaced with current ones before verification.
  - Whether the Q11 clearance covers the PNMB reproduction notice is `[verify]`.

## ADR-021 — Launch in Vietnam first (answers Q1)
- **Date:** 2026-09-30 · **Status:** Accepted
- **Context:** The founder chose Vietnam as the launch market. SG/MY (English, common law) were planned first, and the code, corpus pipeline and playbooks are SG/MY-oriented.
- **Decision:**
  - The VN pilot plan in `docs/14-vietnam-launch-plan.md` (workstreams V0–V9) takes priority over SG/MY feature work; SG/MY stay built and green.
  - Vietnamese is the authoritative legal language: only official Vietnamese text enters the index, and English renderings are labelled unofficial.
  - Bilingual VI–EN review (alignment, discrepancy detection, prevailing language) is launch-critical.
  - Client data of VN tenants stays in a VN cell by default. Offshore processing, including frontier escalation, needs a per-firm opt-in backed by consent and a transfer dossier.
  - Cross-lingual dense retrieval becomes a launch requirement.
- **Consequences:**
  - New work: VN corpus parser (Điều/Khoản/Điểm, legacy encodings), a VN cell (infra), a Vietnamese UI, VN playbooks with a VN legal engineer, and T1 selection on Vietnamese.
  - The pilot depends on VN1–VN8 (docs/13).
  - All VN legal references in the plan are `[verify]` until a VN lawyer confirms them.

## ADR-022 — Economical MVP pilot: Coolify on Contabo, scraped official texts, hosted model APIs (supersedes ADR-021's VN-cell default)
- **Date:** 2026-09-30 · **Status:** Accepted
- **Context:** For the MVP phase the founder chose the cheapest workable pilot. That means hosting with Coolify on a Contabo VPS, legal materials scraped from public Vietnamese sites, and a launch scope of NDA, commercial contracts, services and DPA.
- **Decision:**
  - **Hosting:** one Contabo VPS (Singapore location preferred) running Coolify, with Postgres/pgvector, API, worker and web as containers. Nightly encrypted off-site backups.
  - **Models:** open-weight models through pay-per-token OpenAI-compatible APIs, with no GPU on the VPS. Multilingual embeddings run on the VPS CPU. No OCR in the pilot.
  - **Residency:** ADR-021's "VN cell by default" is replaced for the pilot by a per-firm `allow_offshore_processing` switch. It is on only after a DPA and a cross-border transfer dossier are in place. Pilot starts with low-sensitivity or anonymised matters.
  - **Legal materials:** scraped from official government sites only, with the polite fetcher and snapshots (ADR-019). Commercial databases are not scraped. The lawyer verification gate is unchanged.
  - **Launch scope:** NDA, commercial contracts (sale/supply of goods), services and DPA.
- **Consequences:**
  - Pilot infrastructure costs tens of euros a month instead of a cloud cell.
  - Data leaves Vietnam (Contabo has no VN region `[verify]`), so the §6 safeguards in docs/14 are mandatory before real client documents.
  - A single VPS is a single point of failure: backups plus a restore drill are required.
  - Containers stay portable to VN hosting later.
