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
