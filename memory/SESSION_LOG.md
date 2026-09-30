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

## 2026-09-30 — Vietnam pilot made release-ready (R1–R7)
- Done:
  - **R1 bilingual reading:** DOCX in body order with table cells, `travo_rag/bilingual.py`
    (four layouts), keyword segmentation (Điều/Article), VN number/amount/date/period parser
    (`travo_agents/numbers.py`), new clause keys and SALE, migration 0005.
  - **R2 discrepancy findings:** `bilingual` step and `bilingual_check` task (migration 0006,
    `findings.evidence`).
  - **R3 drafts:** VN playbooks `nda_vn`, `commercial_vn`, `services_vn`, `dpa_vn` and
    `jurisdiction_packs/vn.yaml`, all `[verify]`.
  - **R4 VN statutes:** `legal_sources/vn.yaml` (15, `url: null`), `parsers_vn.py`, unaccented
    search (migration 0008), NFC citations, Vietnamese pinpoints.
  - **R5 routing:** offshore switch, `default_policy_vn.yaml`, endpoint `zdr`/`languages`,
    output language (migration 0007).
  - **R6 UI and exports:** Vietnamese UI (`i18n/`), bilingual canvas, VI/EN/both exports,
    two-column bilingual redline.
  - **R7 release gate:**
    - `evals/vn_gold.py` with gates in `make eval` and `tests/test_vn_evals.py`;
    - sign-in rate limit (`ratelimit.py`, BFF sends `X-Travo-Client-IP`);
    - VN e2e; deploy smoke includes a bilingual review; `TRAVO_DEFAULT_LOCALE=vi`.
  - **Fixes the eval found:** longest taxonomy hint wins ties; Latin-1 tone marks count as
    Vietnamese; hours/days/working days are periods.
- Decisions: ADR-023.
- Gates: make check (183 passed), web-check, e2e (7), eval (VN gates 1.000 on the synthetic set),
  deploy-smoke — all green.
- Next:
  - deploy to the VPS (SSH access + domain);
  - `legal-fetch -j VN` on the VPS (URLs to discover), then ingest and `legal-verify`;
  - lawyer sign-off of the playbooks and pack;
  - real-contract gold set; DPA and transfer dossier (docs/14 §6).
- Open threads: T1 in Vietnamese is untested (no key); synthetic evals may overstate quality;
  the in-process rate limit assumes one API process.

## 2026-09-30 — Pilot deployment packaging for the existing Coolify VPS (V6)
- **Done:**
  - **Deploy files:** `deploy/` — Dockerfile.api (api + worker, non-root, healthcheck, `migrate` on start), Dockerfile.web (Next standalone), docker-compose.coolify.yml (only `web` public), backup.sh, .env.example.
  - **Production guard:** `TRAVO_ENV=production` refuses to start with unsafe settings (dev tokens, inline reviews, unverified sources allowed, bad master key or JWT secret, default DB passwords).
  - **https-only identity providers** in production.
  - **New command:** `travo migrate`, which runs alembic and creates/updates the app role from `TRAVO_DATABASE_URL`.
  - **Smoke test:** `scripts/deploy_smoke.py` + `deploy/smoke.override.yml`. The stack built from these files passed locally: SSO, CSP, CSRF, and a review completed by the worker.
  - Runbook `docs/runbooks/deploy-coolify.md`. Tests: 142 pytest, 26 vitest, 6 e2e.
- **Next:**
  1. The user grants SSH/Coolify access → deploy per the runbook.
  2. V1 VN corpus (needs the VN legal domains allowed, or scrape on the VPS).
  3. V3 bilingual review.
- **Open threads:**
  - Coolify's native backups for compose-embedded databases `[verify]`; the scheduled task + host rclone crypt is the documented path.
  - Sign-in rate limiting and a pen test before paid launch.

## 2026-09-30 — Vietnam pilot decisions (economical MVP)
- **Done:**
  - Recorded the founder's decisions: Coolify on a Contabo VPS; legal materials scraped from official VN sites; launch scope NDA / commercial contracts / services / DPA.
  - Revised docs/14 to v2: §6 pilot data-protection safeguards, §12 topology, sizing and cost, V6 now the pilot deployment, V2 CPU embeddings, V5 hosted APIs. Updated docs/13 (VN1, VN3, VN4, VN5 decided).
  - Checked reachability: vbpl.vn and the other .gov.vn legal sites are blocked by this dev environment's network policy (proxy 403).
- **Decisions:** ADR-022 (supersedes ADR-021's VN-cell default).
- **Next:**
  1. Allow the VN legal domains in the environment network settings, or run the scraper on the VPS.
  2. V1: `vn.yaml` + `vbpl_html`/DOCX fetch + `parsers_vn.py` against real pages.
  3. V6: Dockerfiles + Coolify compose + deploy runbook.
  4. V3: bilingual alignment + discrepancy checks.
- **Open threads:**
  - Contabo has no VN region `[verify]`; the transfer dossier and DPA are needed before real client data.
  - VN2 (entity) is due before paid conversion.

## 2026-09-30 — Vietnam-first launch plan
- **Done:**
  - The founder decided to launch in Vietnam first (Q1 → ADR-021).
  - Wrote `docs/14-vietnam-launch-plan.md`: scope, VN legal corpus (sources, 15 launch instruments `[verify]`, parser and search changes), bilingual review (alignment, discrepancy checks, prevailing language, VN machine checks), models and routing, residency and compliance, Vietnamese UX, eval gates, workstreams V0–V9, decisions VN1–VN8, risks.
  - Updated docs/01, 12 and 13, and CLAUDE.md.
  - No code changes.
- **Decisions:** ADR-021.
- **Next:**
  1. Founder answers to VN1–VN8.
  2. Get official Vietnamese texts (vbpl.vn DOC/HTML) for BLDS 2015 and LTM 2005 to build `parsers_vn.py` against real documents.
  3. Start V1 + V3.
- **Open threads:**
  - All VN legal references are from memory `[verify]`.
  - The MY corpus inputs are still pending (lower priority now).

## 2026-09-30 — P1 slice 5: parser hardened on real AGC reprints; MY Acts imported
- **Done:**
  - **Inputs:** the founder supplied 4 AGC Malaysia PDFs:
    - Contracts Act 1950 (Act 136)
    - PDPA 2010 (Act 709)
    - Act 347
    - Act 237 (Malay)

    They also confirmed Q11.
  - **Parser rewrite:** the real files exposed silent line loss and other failures. The splitter is now contents-driven and page-aware:
    - chrome is removed only at page edges;
    - `*NOTE` footnotes are set aside;
    - headings and Part lines are matched to the contents (close match for contents typos);
    - Malay end markers and dates are handled;
    - an accounting check catches any dropped text.
  - **Results:** all 4 Acts parse with section numbers identical to their contents tables (191/146/34/14) and zero unplaced text.
  - **Import and UI:**
    - `legal-import` command for supplied files (`origin: supplied`).
    - Snapshots are never overwritten.
    - The report shows notes, Part labels, stats and manifest notes.
    - API and drawer show the issuing body.
  - **Tests:** 5 new synthetic tests, plus env-gated real-PDF tests including ingest → retrieval → API. All checks green.
- **Decisions:** ADR-020.
- **Next:**
  1. Get the current MY reprints (the Contracts Act text is as at 2006; the PDPA as at July 2023, before the 2024 amendments [verify]) and their official URLs. Then have a lawyer review `out/legal/my-review.md` and run `legal-verify`.
  2. Remaining MY Acts: 646, 137, 254, 658. Then SG via `legal-fetch`.
  3. Ingest schedules and appendices (e.g. Contracts (Amendment) Act 1976 scholarship provisions).
- **Open threads:**
  - Does the Q11 clearance cover the PNMB reproduction notice? [verify]
  - Split-word PDF artefacts ("di -Pertua") are kept verbatim.
  - Acts 347/237 are used only as parser samples, not in the manifest.

## 2026-09-30 — P1 slice 4: official-statute pipeline + lawyer verification
- **Done:**
  - **Manifests:** `config/legal_sources/{sg,my}.yaml` with 8 SG instruments (SSO HTML) and 6 MY instruments (AGC PDF, `url: null` until filled).
  - **Pipeline (`travo_rag.sources`):**
    - polite fetcher (robots.txt, rate limit, retries, size cap);
    - immutable raw snapshots with sha256 metadata;
    - HTML/PDF parsers with a shared section splitter;
    - title and minimum-section guards;
    - JSONL plus a Markdown review report.
  - **Verification:** migration 0004 adds provenance and `review_status` to `legal_sources`. A new snapshot resets verification. `legal-verify` CLI. `TRAVO_REQUIRE_VERIFIED_SOURCES` retrieval filter. The sources drawer shows "Not yet checked by a lawyer" and the retrieval date. The API returns status and provenance.
  - **Docs:** runbook `docs/runbooks/legal-ingestion.md`; docs/04 §9; Q11 (terms of use).
- **Decisions:** ADR-019.
- **Next:**
  1. On a machine with portal access: fill the MY URLs, `make legal-fetch`, fix parsers against the real SSO/AGC layouts, ingest, and have a lawyer run `legal-verify`.
  2. Real T1 endpoint + evals on real NDAs.
  3. Pre-pilot hardening: SCIM, domain verification, sign-in rate limits, pen test, cloud.
- **Open threads:**
  - Parsers are tested only on synthetic pages; the real layouts are `[verify]`.
  - HTML chrome changes will force re-verification; consider hashing the extracted text as well.
  - Terms of use (Q11) are still open.

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
