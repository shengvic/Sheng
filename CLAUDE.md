# CLAUDE.md — Travo project memory (read this first)

**Travo** is an agentic legal-process platform for law firms in Southeast Asia
(Vietnam, Singapore, Indonesia, Malaysia). Wedge product: **contract & agreement
review**. It acts as a "digital senior associate": it runs long legal workflows on
a domain-tuned open-weight model pipeline, grounds every claim in retrieved
legal sources with per-claim citation checks, and escalates hard sub-tasks to
frontier models through a **model-agnostic, conflict-aware router**.

## Current phase
- **Phase:** P0 — specs complete, no application code yet.
- **Next step:** start P0 foundations (see `docs/12-roadmap.md` §P0).
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

## Planned repo layout (once code starts, per docs/10)
```
apps/web          Next.js workspace UI
apps/word-addin   Office.js add-in
services/api      FastAPI gateway + tenancy/auth
services/agents   orchestrator + sub-agents (LangGraph)
services/router   model router / LLM gateway
services/rag      ingestion, indexing, retrieval, citation validator
services/flywheel telemetry, datasets, eval + training jobs
packages/schemas  shared types (OpenAPI / JSON Schema)
infra/            Terraform, Helm
evals/            golden sets + harness
```
