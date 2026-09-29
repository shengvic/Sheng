# 10 — Tech Stack

> **Status:** Draft v1 · **Last updated:** 2026-09-29 · **Related:** [02](02-system-architecture.md), [12](12-roadmap.md)

Chosen for **time to market** with a small team, while keeping every piece swappable.

| Layer | Choice | Why / swap path |
|---|---|---|
| Frontend | Next.js (React, TypeScript), Tailwind + shadcn/ui, TanStack Query | Fast iteration, SSR for auth pages |
| Document rendering | docx-preview / PDF.js; own clause-anchor overlay | Anchor findings to spans |
| Word add-in | Office.js (TypeScript), shared components with web | Required for lawyer adoption |
| API & services | Python 3.12, FastAPI, Pydantic v2 | Best ML/LLM ecosystem; typed schemas |
| Agent orchestration | LangGraph (graph + state), wrapped behind Travo's `Agent` interface | Swappable; no framework lock-in in domain code |
| Durable workflows | Temporal (Cloud early, self-host later) | Multi-hour, resumable, human-pausable reviews |
| LLM gateway / router | LiteLLM (OpenAI-compatible proxy) + Travo policy engine in front | Multi-provider, BYO keys, cost tracking; OpenRouter as proxy upstream |
| Open-weight inference | Fireworks AI / Baseten (P0–P3) → vLLM / SGLang on Travo GPUs (P4) | Multi-LoRA serving; OpenAI-compatible |
| Primary DB | PostgreSQL 16 (RLS), managed (RDS/Cloud SQL) | Tenancy via RLS |
| Vector search | pgvector (P0–P2) → Qdrant / OpenSearch k-NN at scale | Keep in Postgres early for simplicity + RLS |
| Lexical search | OpenSearch (BM25, multilingual analyzers incl. vi/id/ms) | Hybrid retrieval |
| Reranker / embeddings | Multilingual open models (e.g., BGE-M3 / multilingual-e5 class + cross-encoder reranker), hosted as T0 | Self-hostable, en/vi/id/ms |
| Parsing / OCR | docx (python-docx), PDF layout parser (e.g., Docling / Unstructured), OCR (PaddleOCR / cloud OCR in-region) | Scanned contracts common in VN/ID |
| Object storage | S3 / GCS with per-tenant prefixes & KMS keys | |
| Events | Postgres outbox → NATS JetStream (or Kafka later) | Simple first |
| Auth | OIDC/SAML via WorkOS / Auth0 / Keycloak; SCIM | Enterprise SSO quickly |
| Secrets / keys | Cloud KMS + Vault (BYO provider keys) | |
| Observability | OpenTelemetry, Grafana/Tempo/Loki; Langfuse (self-hosted, per-cell) for LLM traces | Content stays in-cell |
| Evals | Custom harness + promptfoo/pytest; golden sets in `evals/` | CI gates |
| Training (P3) | Hugging Face TRL / Axolotl / Unsloth; managed GPUs (Fireworks fine-tuning, Together, Modal, or cloud) | LoRA SFT + DPO |
| Infra | Terraform, Kubernetes (EKS/GKE) + Helm; one stack per region cell | Reproducible cells |
| CI/CD | GitHub Actions; preview envs; eval gates on prompt/model changes | |

## P0 deviations (as built, 2026-09-29)
| Planned | As built in P0 | Why / when it changes |
|---|---|---|
| LiteLLM gateway | Own `OpenAICompatibleProvider` (httpx) behind the `Provider` interface | Fewer moving parts; LiteLLM can sit behind the same interface when needed (ADR-009) |
| Separate services | Modular monolith, in-process packages (ADR-008) | Split when scaling/ownership requires |
| pgvector | Not yet used | Embeddings start in P1 retrieval work |
| Temporal | Inline synchronous pipeline | Durable workflows needed for multi-step P1 reviews |
| Cloud KMS | `LocalKms` (AES-GCM master key from env) behind `Kms` protocol | Swap per deployment |
| S3/GCS | `LocalEncryptedStore` behind `ObjectStore` protocol | Swap per deployment |
| Python 3.12 | 3.11+ supported (container has 3.11) | — |

## Monorepo layout
See `CLAUDE.md` → "Repo layout". Tooling: `pnpm` workspaces (TS), `uv` (Python), `make` targets for dev (`make dev`, `make test`, `make eval`).

## Engineering conventions
- Prompts are versioned files (`services/agents/prompts/<agent>/<version>.md`) with eval cases; no inline prompt strings.
- Every model call through the router client; lint rule forbids importing vendor SDKs outside `services/router`.
- `tenant_id` / `matter_id` propagated via request context; DB sessions set `app.tenant_id` for RLS.
