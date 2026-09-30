# 08 — UX / UI Specification

> **Status:** Draft v1 · **Last updated:** 2026-09-30 · **Related:** [05](05-contract-review-workflow.md), [07](07-hitl-telemetry-data-flywheel.md)

## 1. Design principles
1. **Lawyer-native:** feels like Word + a sharp associate's issues list, not a chatbot. Chat exists but is secondary.
2. **Show the evidence:** every finding has visible sources, confidence and the playbook rule it applies.
3. **One-click teaching:** correcting Travo is faster than ignoring it; every correction visibly improves Travo.
4. **Transparent machinery:** which model ran, why, what it cost — available on demand, never in the way.
5. **Calm, professional aesthetic:** neutral palette, dense but legible tables, keyboard-first, light/dark themes; localised UI (EN, VI, ID, MS).

## 2. Surfaces
| Surface | Phase | Purpose |
|---|---|---|
| Web workspace | P1 | Matters, review canvas, playbooks, admin |
| Word add-in (Office.js) | P2 | Review/redline inside the document the lawyer already has open |
| Outlook add-in | P4 | Intake: "review this attachment" |
| Admin console | P1 (basic) → P2 | Model policy, walls, residency, spend, audit |

## 3. Key screens
### 3.1 Matter home
- Matter header: client, matter no., jurisdiction(s), wall badge (🔒 members), model-policy badge (e.g., "No OpenAI · SG residency").
- Document list with status (processing / ready / in review / final), progress streaming.
- "Start review" → choose or confirm playbook (pre-selected by classifier with confidence).

### 3.2 Review canvas (core)
```
┌───────────────────────────── Matter: Acme / SPA ─────────── [Export ▾] ┐
│ Document (rendered, clause-anchored)    │ Findings (filter: severity,  │
│                                         │ status, clause, jurisdiction)│
│ 12.1 Limitation of liability ▌◀────────▶│ ● HIGH  Liability cap        │
│   highlighted, redline inline           │   Playbook: 12m fees (std)   │
│                                         │   Found: uncapped            │
│                                         │   ⚖ SG UCTA s.2 ✅  [chip]   │
│                                         │   Confidence 0.91 · T1       │
│                                         │  [Accept] [Edit] [Reject ▾]  │
│                                         ├──────────────────────────────┤
│                                         │ Sources panel (on chip click)│
│                                         │  official text + translation │
└─────────────────────────────────────────┴──────────────────────────────┘
```
- Keyboard: `J/K` next/prev finding, `A` accept, `E` edit, `R` reject (opens reason codes), `S` sources.
- Citation chips: ✅ supported, ⚠️ partial, ❌ unsupported; click → sources panel with pinpoint highlight and in-force status.
- "Why this model?" link on each finding → routing decision (tier, provider, escalation reason, cost).
- Bilingual view toggle: side-by-side language versions with discrepancy markers.

### 3.3 Playbook editor
- Structured table per clause: standard / fallbacks / unacceptable / severity / redline template / law refs.
- Version history with diffs and authors; "test against sample contracts" button (runs mini-eval).
- **Suggestions inbox**: Travo-proposed playbook updates derived from repeated corrections ([07](07-hitl-telemetry-data-flywheel.md) §6), each with evidence (which edits, by whom).

### 3.4 Tabular review (P2)
Grid: rows = documents, columns = extracted terms/questions; each cell has citation to the clause; bulk accept; export XLSX.

### 3.5 Admin console
- Model policy editor (form over the YAML in [03](03-model-routing-and-hybrid-inference.md)); dry-run showing which models each task would use.
- BYO key management (masked, tested, rotated).
- Ethical walls: members, screened users, import from Intapp/iManage.
- Spend dashboard: cost per matter, per task type, T1 vs T2 share.
- Audit log search and export.

### 3.6 "Travo is learning" panel (self-adaptive loop, visible)
Weekly digest per practice group:
- Acceptance rate trend, top corrected clause types, new playbook suggestions.
- "Adapter v8 promoted: +6 pts acceptance on MSAs" (P3).
- Items where Travo is still weak → invites expert reviewers to label a small batch.

This makes improvement a visible, shared process between Travo and the firm, and gives Travo product teams aggregate (non-content) quality signals to prioritise work.

## 4. Feedback UX details
- Reject → required reason code (1 click) + optional note.
- Edit → inline diff captured automatically; optional "apply to playbook" checkbox.
- Batch actions for low-severity standard findings.
- Undo for 10 s on every action.

## 5. Accessibility & localisation
WCAG 2.2 AA; full keyboard navigation; UI strings via i18n (en, vi, id, ms); date/number formats per locale; legal-source language shown with official-language label.

## 6. Product iteration instrumentation (for Travo)
- Privacy-safe product analytics (event names and timings only, no content) per screen.
- In-app feedback button with screenshot redaction.
- Feature flags per tenant for staged rollouts and A/B tests of prompts/models (with eval gates).

## 7. As built — P1 slice 2 (2026-09-29)
`apps/web` (Next.js 16 App Router, TypeScript strict, Tailwind 4, TanStack Query). Client-side
data fetching through a same-origin proxy (`/api/*` → API), dev-token sign-in (ADR-017).

| Screen | Route | Built |
|---|---|---|
| Sign in | `/login` | Dev token paste; OIDC replaces it before pilots |
| Matters | `/matters` | List + create (jurisdictions, conflict-blocked providers) |
| Matter home | `/matters/[id]` | Wall + model-policy badges, drag-drop upload, classification chips, playbook picker, start review, reviews with live step progress |
| Review canvas | `/reviews/[id]` | Step progress (polling), executive summary, export gate bar with jump-to blockers, document pane (clauses, severity badges, accepted/edited wording as tracked insertions/deletions, missing-clause ghost blocks), findings pane (filters, counts, cards with citation chips, redline diff, Why-this-model, override for partner/KM/admin), sources drawer (FIXTURE banner), undo toast, shortcuts help |
| Playbooks | `/playbooks` | Read-only list + rule table (firm and starter) |

Keyboard: `J/K` or arrows move, `A` accept, `E` edit, `R` reject (reason required), `D` defer,
`S` first source, `Esc` close, `?` help. Undo uses the `reset` disposition server-side, so it is
recorded in telemetry and audit like any other action.

Not yet: admin console (policy editor, keys, spend UI), tabular review, Word add-in, SSE,
vi/id/ms dictionaries (strings are centralised in `src/i18n/en.ts`), "Travo is learning" digest.

## 8. As built — sign-in and admin console (2026-09-29)
- **Sign-in:** work email → "Continue with single sign-on" → firm IdP → back to the page the user
  wanted. Clear messages for unknown domains, cancelled sign-in, unavailable IdP. A development
  token form appears only when `TRAVO_DEV_LOGIN=true`.
- **Admin console** (`/admin`, admin role; nav item hidden for others; API enforces it):
  - *Model policy* — YAML editor with server validation and versioning; "Test the policy" shows
    the ordered models a task would use and why each other endpoint is skipped (works on unsaved
    edits); endpoint catalogue.
  - *API keys* — add/rotate/revoke BYO keys; only the last 4 characters are ever shown.
  - *Spend* — total spend, model calls, frontier share; bars of model calls by task, tier and
    matter (cost printed per bar; walled matters appear by id only).
  - *Audit log* — filter by action.
  - *Sign-in (SSO)* — issuer, client id, write-only secret, email domains, enable; active
    sessions with revoke (revoking your own signs you out).

## 9. As built — Vietnamese UI and bilingual canvas (2026-09-30)
- **Locales:**
  - `apps/web/src/i18n/{en,vi}.ts` share one `Dict` type, so a missing key fails the build.
  - Components read strings via `useT()`.
  - The locale comes from the `travo_locale` cookie, else `TRAVO_DEFAULT_LOCALE` (`vi` in the
    pilot), else English. `<html lang>` follows it.
  - The VI/EN switch is in the shell and on the sign-in page.
- **Matter page:** a bilingual-layout chip on each document, and an output-language choice when
  starting a review.
- **Review canvas:**
  - Bilingual clauses show as VI | EN columns.
  - Discrepancy findings show both versions' spans side by side, plus a prevailing-language
    badge, and have their own filter ("Bản Việt / Anh").
  - With output `both`, the alternate-language redline is shown under the main one.
- **Sign-in errors** now include `rate_limited` (HTTP 429 from the API).
