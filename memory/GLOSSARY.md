# Glossary

| Term | Meaning |
|---|---|
| **Matter** | A client engagement/file; Travo's primary security boundary. |
| **Ethical wall** | Information barrier preventing specific lawyers from accessing a matter (conflicts, lateral hires). |
| **Conflict profile** | Per-matter settings, incl. AI providers that must not process the matter's data. |
| **Playbook** | A firm's structured negotiating positions per clause: standard, fallbacks, unacceptable, severity. |
| **Jurisdiction pack** | Travo-maintained set of local-law rules, sources and starter playbooks for one jurisdiction. |
| **Clause taxonomy** | Canonical list of clause keys (e.g., `limitation_of_liability`, `governing_law`). |
| **Finding** | A detected issue on a clause vs playbook or law, with severity, citations, suggested redline. |
| **Disposition** | Lawyer's action on a finding: accept / edit / reject / defer (+ reason code). |
| **Pinpoint citation** | Reference to the exact article/section/paragraph supporting a claim. |
| **Per-claim validation** | Checking each atomic legal proposition for a supporting, in-force source. |
| **Export gate** | Rule blocking export while unsupported claims or undispositioned findings remain. |
| **T0 / T1 / T2** | Model tiers: utility, Travo domain open-weight, frontier proprietary. |
| **Escalation** | T1 asking T2 for help on a sub-task beyond its competence. |
| **Task Descriptor** | Structured router input describing a model call's needs and constraints. |
| **RoutingDecision** | Logged record of how/why a model was chosen. |
| **BYO keys** | Firm's own provider API keys used by Travo's router. |
| **Travo Tokens** | Prepaid usage credits via Travo's proxy and hosted models. |
| **Region cell** | Independent deployment stack per data-residency region (SG, VN, ID). |
| **LoRA adapter** | Lightweight per-firm fine-tuned weights applied on a shared base model. |
| **SFT / DPO** | Supervised fine-tuning / Direct Preference Optimisation. |
| **Golden set** | Expert-labelled evaluation data used as release gates. |
| **ZDR** | Zero data retention agreement with a model provider. |
| **RLS** | Row-level security in Postgres, enforcing tenant isolation. |
| **Review run** | One durable execution of the review workflow over a document with a pinned playbook version. |
| **Step** | A named, checkpointed unit of a review run (`prepare`, `compare`, `lawcheck`, `redline`, `memo`). |
| **Jurisdiction pack** (as built) | YAML of law-check triggers and retrieval queries per jurisdiction; contains no legal text. |
| **Fixture corpus** | Synthetic legal units used in tests, titled "FIXTURE — not law". |
| **Few-shot memory** | Reusing the firm's accepted/edited redlines as examples, limited to matters the user may see. |
| **needs_human** | Finding status when no permitted model could produce a validated answer. |
| **BFF** | Backend-for-frontend: the Next.js server routes (`/api/*`, `/auth/*`) that hold the session and call the API for the browser. |
| **Session token** | Travo JWT with a `sid` claim backed by a revocable `auth_sessions` row; lives only in an httpOnly cookie. |
| **PKCE** | Proof Key for Code Exchange: binds the OIDC authorization code to the client that started sign-in. |
| **Dev token** | Session-less token from `mint-token`/`dev-token`; only accepted when `TRAVO_ALLOW_DEV_TOKENS=true`. |
| **Raw snapshot** | Unchanged copy of an official page/PDF as downloaded, with URL, time and sha256 in `.meta.json`. |
| **Review report** | Markdown output of `legal-fetch` (status, warnings, sample sections) that a legal engineer checks before ingesting. |
| **Verified source** | A `legal_sources` row a lawyer has checked against the portal (`legal-verify`); resets when the snapshot changes. |
| **Supplied snapshot** | An official file obtained by hand and stored with `legal-import` (`origin: supplied`); same review and verification path as a fetched one. |
| **Contents-driven parsing** | Using an Act's "Arrangement of Sections" to decide which numbered lines start sections and which lines are headings or Part titles. |
| **Editorial note** | A reprint footnote (`*NOTE—…`); shown in the review report, never ingested as law. |
| **Bilingual layout** | How a VI–EN contract pairs its versions: `table` (VI \| EN columns), `inline`, `paragraphs` (alternating) or `halves` (all VI, then all EN). Stored on `documents.bilingual_layout`. |
| **Clause pair** | A clause's primary-language text (`text`) with its other-language version (`text_alt`). |
| **Discrepancy finding** | A `kind = bilingual` finding: the two language versions of a clause differ (amounts, figures vs words, periods, dates, negation, meaning…). |
| **Prevailing language** | The version a contract says governs if the two differ ("bản tiếng Việt được ưu tiên áp dụng"). |
| **Figures vs words** | A check that an amount in digits matches the same amount written in words ("100.000.000 đồng (Bằng chữ: Một trăm triệu đồng)"). |
| **Điều / khoản / điểm** | Vietnamese article / numbered clause (1., 2.) / lettered point (a), b)); the unit hierarchy of VN legislation and contracts. |
| **Output language** | The language of a review's findings, redlines and memo (`vi`, `en` or `both`), separate from the UI locale. |
| **Offshore switch** | `data_location.allow_offshore_processing` in the model policy; off until the DPA and cross-border transfer dossier exist. |
