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
