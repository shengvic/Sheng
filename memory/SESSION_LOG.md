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

## 2026-09-29 — P1 slice 3: SSO sign-in + admin console
- **Done:** Per-firm OIDC sign-in (auth code + PKCE; API-side code exchange and id_token validation; subject binding; no JIT), revocable server-side sessions, global one-firm-per-domain rule, SECURITY DEFINER sign-in lookups, dev tokens gated by `TRAVO_ALLOW_DEV_TOKENS`. Web: Next BFF (`/auth/*`, `/api/*` proxy adding the token from an httpOnly cookie), CSRF header + Origin checks, per-request nonce CSP in `proxy.ts`, new login page, admin console (model policy editor + dry-run, BYO keys, spend bars, audit, SSO settings + sessions). Mock OIDC provider (`scripts/mock_oidc.py`) for pytest and e2e; `configure-idp` CLI. Tests: 117 pytest, 26 vitest, 6 Playwright specs (SSO review flow, admin flow, CSP header + no CSP violations, CSRF refusal, partner denied admin, dev-token path).
- **Decisions:** ADR-018 (supersedes ADR-017's auth).
- **Next:**
  1. Real legal corpus fetchers (SSO/AGC) + lawyer spot-check.
  2. Real T1 endpoint + evals on real NDAs; more starter playbooks.
  3. Pre-pilot hardening: SCIM, email-domain verification, rate limiting on `/v1/auth/*`, pen test, cloud deployment (Terraform SG cell).
- **Open threads:** CI jobs (web, e2e) still not run on GitHub. `style-src` allows inline styles. Domain claims are unverified. Eval scores remain synthetic.

## 2026-09-29 — P1 slice 2: review canvas web UI
- **Done:** `apps/web` (Next.js 16, TS strict, Tailwind 4, TanStack Query): sign-in (dev token), matters list/create, matter home (upload, classification, playbook picker, start review, live progress), review canvas (document pane with tracked-change previews and missing-clause blocks, findings pane with filters, citation chips, sources drawer, Why-this-model, edit/reject-with-reason/defer/accept, citation override, undo, keyboard shortcuts, export gate bar, DOCX download), playbooks view; light/dark themes. API: `/v1/me`, `/v1/legal-units/{id}`, `/v1/reviews/{id}/routing`, `reset` disposition, `travo dev-token`. Tests: 99 Python, 17 vitest, 1 Playwright e2e (full lawyer flow incl. dark-mode check) via `scripts/e2e.sh`. CI jobs for web + e2e added (not yet run on GitHub).
- **Decisions:** ADR-017.
- **Next:**
  1. Real OIDC sign-in (replace dev token) + CSP; admin console UI (policy editor, BYO keys, spend).
  2. Real SG/MY legal corpus ingestion (fetchers) and lawyer spot-check.
  3. Real T1 endpoint + evals on real NDAs; more starter playbooks.
  4. Design-partner demo script using `make dev-token` + `make web-dev`.
- **Open threads:** Next 16 dev blocks dev assets for `127.0.0.1` origins — use `localhost` (e2e does). Token in `sessionStorage` is dev-only (ADR-017). Eval scores remain synthetic.

## 2026-09-29 — P1 slice 1: backend review engine
- **Done:** Durable Postgres review runner (resume/retry/backoff/leases; cross-tenant claim via one SECURITY DEFINER function). Starter playbooks NDA SG/MY with machine-checkable rules; firm playbook versioning API. Agents: playbook compare, law check (jurisdiction packs SG/MY), redline (few-shot from firm edits, wall-scoped), memo; prompts moved to versioned files. Legal index + JSONL ingestion CLI, full-text retrieval with in-force filters, per-claim citation validator (existence, in-force, quote fidelity, entailment via router). Escalation T1→T2 on low confidence / failed citations; conflict-blocked → needs_human. Findings dispositions with reason codes, citation overrides, telemetry. Export gate; redline DOCX with Word tracked changes; memo DOCX. Admin spend view. 94 tests; ruff + mypy clean; live smoke (server + `travo worker` + curl) passed.
- **Decisions:** ADR-013..016.
- **Next:**
  1. Review canvas web UI (Next.js) on the new API — next slice per user's choice.
  2. Real SG/MY legal corpus: write SSO/AGC fetchers and run ingestion from an environment with access; lawyer spot-check.
  3. Real T1 endpoint + evals on real NDAs (Q5/Q6); more starter playbooks (MSA, SaaS/DPA, distribution).
  4. pgvector dense retrieval; OCR; signing-date extraction; SSE progress.
- **Open threads:** Eval scores (100%) are on synthetic gold docs written alongside the rules — not a quality claim. BYPASSRLS role creation on managed Postgres `[verify]`. Law is checked "as of today" until signing dates are extracted.

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
