# Session Log

Append a new entry at the top at the end of every working session.
Template:
```
## YYYY-MM-DD — <short title>
- Done:
- Decisions: (link ADRs)
- Next:
- Open threads / blockers:
```

---

## 2026-09-29 — P0 foundations: first implementation slice
- **Done:** Modular monolith scaffold (uv, Makefile, CI, docker-compose). Postgres schema + RLS on all tenant tables with a non-owner app role; composite FKs keep rows within a tenant. Dev JWT/OIDC auth; ethical walls (admins included, 404 + audit on denial). Envelope-encrypted document storage and BYO key vault. Router v0 (policy engine, vendor/host conflict rules, residency, BYO/proxy, budgets, escalation, fallback, decision log, dry-run API). Parsing (DOCX/PDF/TXT), language ID (en/vi/id/ms heuristic), clause segmentation (incl. Điều/Pasal/Fasal). Classify + clause-extraction agents via router; `travo_rules` T0 model. Append-only audit + routing logs. Eval harness + 3 synthetic gold NDAs. 64 tests; ruff + mypy clean; live smoke test (uvicorn + curl) passed.
- **Decisions:** ADR-008..012.
- **Next:**
  1. Configure a real T1 endpoint (Fireworks/Baseten) and run evals against it (needs Q5/Q6 answers + API key).
  2. Replace synthetic gold set with 30 real annotated SG/MY NDAs. Current 100% scores are on synthetic docs written alongside the rules — not a quality claim.
  3. Terraform SG cell; real OIDC IdP + SCIM; OTel + Langfuse.
  4. Start P1: Temporal workflow, playbook compare agent, legal RAG (pgvector + OpenSearch), citation validator, web UI.
- **Open threads:** Scanned PDFs return `unsupported` (OCR in P1). Pipeline runs inline in the upload request. Model ids in `config/endpoints.yaml` are placeholders `[verify]`.

## 2026-09-29 — Initial specs and roadmap
- **Done:** Competitive analysis (Harvey, Legora); full spec set docs/00–13; CLAUDE.md memory entry point; ADR-001..007; glossary.
- **Decisions:** ADR-001 to ADR-006 accepted; ADR-007 proposed.
- **Next:**
  1. Founder answers to `docs/13-open-questions.md` (esp. Q1 market, Q2 legal data licences, Q5/Q6 model + host).
  2. Start P0 (`docs/12-roadmap.md`): monorepo scaffold, SG cell Terraform, auth/tenancy/RLS, router v0.
  3. Collect 30 NDAs (SG/MY) for the first eval set; recruit 2–3 design-partner firms.
- **Open threads:** Competitor facts and law references marked `[verify]` need checking before external use.
