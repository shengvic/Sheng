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
