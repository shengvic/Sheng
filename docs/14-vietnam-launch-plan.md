# 14 — Vietnam-First Launch Plan

> **Status:** Draft v3 (pilot release-ready, ADR-023) · **Last updated:** 2026-09-30 · **Related:** ADR-021, ADR-022, [01](01-product-vision-and-prd.md), [04](04-legal-rag-and-citation-validation.md), [05](05-contract-review-workflow.md), [06](06-security-compliance-ethical-walls.md), [08](08-ux-ui-spec.md), [11](11-evaluation-and-quality.md), [12](12-roadmap.md), [13](13-open-questions.md)
>
> **Legal references in this document are from memory as of 2026-09-30. Every instrument number,
> article and date is `[verify]` until a Vietnamese-qualified lawyer confirms it against the
> official text. None of it may enter the legal index except through the source pipeline (ADR-014).**

## 1. Decision and what it changes
The founder decided on 2026-09-30 to **launch in Vietnam first** (Q1, ADR-021). Singapore and
Malaysia stay built and supported, but they move behind Vietnam. What changes:

| Area | SG/MY assumption so far | Vietnam-first |
|---|---|---|
| Legal system | Common law, English statutes | Civil law. Vietnamese is the only authoritative text; English translations are unofficial. Official precedents (án lệ) are a secondary source. |
| Contracts | English | **Bilingual VI–EN** (foreign-investment work) or Vietnamese only. Which language prevails matters. |
| Structure | Section 12(1)(a) | **Điều 12, Khoản 1, Điểm a** within Phần / Chương / Mục |
| Law sources | SSO HTML, AGC PDFs | vbpl.vn (national legal database), Công báo (official gazette), consolidated texts (văn bản hợp nhất), án lệ |
| Retrieval | English full text | Vietnamese full text with and without diacritics, plus **cross-lingual** search (English clause → Vietnamese law). Dense retrieval becomes a launch requirement. |
| Data law | PDPA SG/MY | PDP Law 2025 + Decree 13/2023 (cross-border transfer dossiers), Cybersecurity Law 2018 + Decree 53/2022 (localisation), Law on Data 2024 `[verify]` |
| Hosting | SG cell (AWS) | **MVP pilot: one Contabo VPS run with Coolify** (ADR-022). Contabo has no Vietnam region `[verify]`, so data leaves Vietnam and the pilot needs the §6 safeguards. VN hosting is an upgrade path, not a pilot requirement. |
| UI | English | **Vietnamese UI**, English as an option; memos in VI or EN |
| Models | English quality | Vietnamese and bilingual quality decide the T1 choice. **Pilot: pay-per-token hosted open-weight APIs** (no GPUs on the VPS). |

## 2. Launch scope (Vietnam MVP)
**Users:** Vietnamese law firms in HCMC and Hanoi that do foreign-investment and commercial work,
and the Vietnam offices of regional firms. Personas as in [01](01-product-vision-and-prd.md): associate,
partner, KM/legal-ops, IT/admin.

**Contract types (decided 2026-09-30, VN5):**
1. NDA / confidentiality agreement (thỏa thuận bảo mật)
2. Commercial contracts — sale and supply of goods (hợp đồng mua bán hàng hóa) and general
   commercial terms
3. Services agreements (hợp đồng dịch vụ)
4. Data processing agreements under the PDP Law (hợp đồng xử lý dữ liệu cá nhân)

Each comes bilingual (VI–EN) or Vietnamese only.

Later: distribution/agency, labour contracts and NDAs with employees (Bộ luật Lao động),
leases, M&A/SPA.

**Launch-critical features:**
- Review of bilingual contracts: clause alignment, **discrepancy detection**, and which language
  prevails.
- Vietnamese law checks grounded in verified Vietnamese sources, with per-claim citations in
  Vietnamese citation style (`Khoản 1 Điều 301 Luật Thương mại 2005`).
- Vietnamese playbooks, a Vietnamese UI, and memos and redlines in VI, EN or both.
- An economical pilot deployment (§12), with the data-protection safeguards in §6.

**Exit criteria for the VN pilot:**
- 2–3 VN design-partner firms using Travo on real non-critical matters.
- ≥ 100 contracts reviewed.
- Finding acceptance ≥ 60%.
- Bilingual discrepancy recall ≥ 90% on the seeded set (§8).
- 0 unsupported legal claims reaching export.

## 3. Legal corpus (Vietnam)

### 3.1 Sources
| Source | Use | Notes |
|---|---|---|
| vbpl.vn — national database of legal documents (Ministry of Justice) | Primary full text; status (còn/hết hiệu lực); relationships (amends, guides, replaces) | Terms of use `[verify]` (VN3). HTML "toàn văn" plus attached DOC/PDF. |
| Công báo (congbao.chinhphu.vn) | Gazette copy used to confirm text and dates | Often scanned PDFs: OCR only as a fallback |
| Văn bản hợp nhất (consolidated texts from the issuing body) | Preferred text when an instrument has been amended | Footnotes mark amended provisions; treat them as notes (as with `*NOTE`, ADR-020) |
| anle.toaan.gov.vn — official precedents | Secondary source (phase 2) | Cite as `Án lệ số NN/YYYY/AL` |
| Commercial databases (Thư Viện Pháp Luật, LuatVietnam) | English translations and annotations | **Not scraped** (their terms restrict copying). Only under licence (Q2). Translations are always labelled "unofficial translation". |

**Scraping policy (decided 2026-09-30, ADR-022):**
- Materials are scraped from **official government sites only**: vbpl.vn, Công báo,
  chinhphu.vn, anle.toaan.gov.vn.
- Vietnamese legal normative documents are excluded from copyright protection (Luật Sở hữu
  trí tuệ, Điều 15) `[verify]`.
- The existing `PoliteFetcher` rules still apply: robots.txt, ≥ 2 s between requests,
  identified User-Agent, size cap, and immutable snapshots with sha256.
- Where it runs: a scheduled Coolify job on the pilot VPS (`legal-fetch -j VN`), or a dev
  environment whose network policy allows those domains.
- vbpl.vn pages can need two steps (the full-text page, then the attached DOC/PDF). The
  manifest stores the document page URL, and the fetcher follows only same-site links that the
  manifest allows.

### 3.2 Launch instruments `[verify all]`
Contract review needs these first; manifest `config/legal_sources/vn.yaml`:

| Id | Instrument | Why |
|---|---|---|
| VN/BLDS2015 | Bộ luật Dân sự 2015 (91/2015/QH13) | Contract formation, validity, penalties (Điều 418), damages, limitation (Điều 429), choice of law for relationships with a foreign element (Điều 663, 683) |
| VN/LTM2005 | Luật Thương mại 2005 (36/2005/QH11) | Commercial penalty cap 8% (Điều 301), damages (Điều 302), penalty plus damages (Điều 307), exemptions and force majeure (Điều 294), limitation 2 years (Điều 319) |
| VN/LTTTM2010 | Luật Trọng tài thương mại 2010 (54/2010/QH12) | Validity of arbitration agreements, foreign arbitration |
| VN/BLTTDS2015 | Bộ luật Tố tụng dân sự 2015 (92/2015/QH13) | Court jurisdiction, recognition of foreign judgments and awards |
| VN/LDN2020 | Luật Doanh nghiệp 2020 (59/2020/QH14) | Signing authority, legal representative, seals |
| VN/LDT2020 | Luật Đầu tư 2020 (61/2020/QH14) | Foreign investors, which relationships have a foreign element |
| VN/LBVDLCN2025 | Luật Bảo vệ dữ liệu cá nhân 2025 (91/2025/QH15, in force 2026) | Processing contracts, consent, cross-border transfer |
| VN/ND13-2023 | Nghị định 13/2023/NĐ-CP | Earlier PDP rules; the transition and what still applies |
| VN/LANM2018 | Luật An ninh mạng 2018 (24/2018/QH14) + Nghị định 53/2022/NĐ-CP | Data localisation |
| VN/LDL2024 | Luật Dữ liệu 2024 (60/2024/QH15) | Core/important data, cross-border transfer |
| VN/LGDDT2023 | Luật Giao dịch điện tử 2023 (20/2023/QH15) | E-contracts, e-signatures |
| VN/LSHTT2005 | Luật Sở hữu trí tuệ (consolidated) | IP assignment and licensing clauses |
| VN/PLNH2005 | Pháp lệnh Ngoại hối (as amended) + implementing circular on foreign-currency use | Pricing and payment in foreign currency between residents |
| VN/BLLD2019 | Bộ luật Lao động 2019 (45/2019/QH14) | Confidentiality and non-compete terms with employees (phase 2 contract types) |
| VN/LCT2018 | Luật Cạnh tranh 2018 | Exclusivity and territorial restrictions (phase 2) |

### 3.3 Pipeline changes (reuse `travo_rag.sources`, ADR-019/020)
- **Formats:**
  - New `vbpl_html` (the full-text page) and `docx`/`doc` import. PDF stays for gazette copies.
  - `legal-import` already covers files downloaded by hand.
- **Encoding normalisation** (new, all VN inputs):
  - Unicode NFC. Convert decomposed tone marks.
  - Detect legacy Vietnamese font encodings (TCVN3/.VnTime, VNI) in old DOC files and convert
    them. Otherwise refuse the file with a clear error; never ingest garbled text.
- **Vietnamese structure splitter** (`parsers_vn.py`, same guarantees as ADR-020):
  - `Điều N. <heading>` starts a unit, with the heading on the same line. Also handle
    `Khoản`/numbered clauses `1.`, points `a)`, and the Phần / Chương / Mục / Tiểu mục labels.
  - `unit_path = "Điều 418"`. Clause and point anchors (`Điều 418.1.a`) are stored as metadata
    for pinpoint display; the unit stays the article.
  - The contents/order check uses strictly increasing Điều numbers. An accounting check ensures
    no text is lost silently.
  - End markers: "Nơi nhận:", signature block ("TM. QUỐC HỘI", "CHỦ TỊCH", "TM. CHÍNH PHỦ"),
    "PHỤ LỤC" (appendices are not ingested at first).
  - Effective date from "có hiệu lực thi hành (kể) từ ngày …". Instrument number and type are
    taken from the header ("Luật số: 91/2015/QH13").
  - Consolidated texts: amendment footnotes become notes. The unit's `effective_from` comes from
    the consolidated date.
- **Validity:** VN instruments are amended and replaced often. Record the relationships from
  vbpl.vn (amends / replaced by / guides). Mark a source `repealed` when it is replaced
  (existing `status` + `effective_to`). The report warns when a newer consolidated text exists.
- **Search:**
  - Add an unaccented full-text column (the `unaccent` extension) so queries typed without tone
    marks still match.
  - Match syllable bigrams, because Vietnamese words span syllables.
  - **pgvector dense retrieval with a multilingual embedding model** (BGE-M3 class) for
    English-clause → Vietnamese-law queries. Fuse with lexical results using the existing RRF
    hook (`travo_rag.retrieval`).
- **Citations:**
  - Vietnamese pinpoint style in validator output and memos.
  - Quote-fidelity checks compare after NFC and whitespace normalisation.
  - English renderings of Vietnamese law are always labelled "unofficial translation" and are
    never quoted as the source.
- **Verification:** unchanged (ADR-019). A Vietnamese-qualified lawyer runs `legal-verify`, and
  `TRAVO_REQUIRE_VERIFIED_SOURCES=true` is set for the pilot.

## 4. Contract processing (Vietnamese and bilingual)
- **Layouts to support:**
  1. A two-column table (VI | EN per row), which is common.
  2. Alternating paragraphs (VI then EN).
  3. Two separate files.
  4. Vietnamese only.

  Extend `travo_rag/parsing.py` to read DOCX tables cell by cell. Scanned contracts need OCR
  with Vietnamese support (PaddleOCR class, run in VN — [10](10-tech-stack.md)).
- **Segmentation:** add Khoản and Điểm to `segmentation.py` (Điều is already there). Handle
  Vietnamese headings (ĐIỀU 1: ĐỊNH NGHĨA) and appendices (Phụ lục).
- **Alignment:** pair VI and EN clauses by numbering, then by cross-lingual embedding similarity.
  Unpaired clauses on either side are findings in their own right.
- **Discrepancy detection:**
  - **T0 deterministic checks:**
    - numbers, percentages, dates ("ngày … tháng … năm …"), amounts and currencies (VND with a
      "." thousands separator);
    - **amount in figures vs amount in words** ("bằng chữ"), which needs a Vietnamese
      number-words parser (một, mươi, trăm, nghìn/ngàn, triệu, tỷ, linh/lẻ, lăm, mốt);
    - party names, tax codes (mã số thuế), time limits, notice periods;
    - negations ("không", "not").
  - **T1/T2 semantic check** per clause pair: obligations, conditions, scope, remedies. Output
    is a structured diff with a severity.
  - **Prevailing-language clause:** detect it ("bản tiếng Việt được ưu tiên áp dụng"). If none
    exists, flag the risk. Severity of each discrepancy depends on which text prevails.
  - New finding type `bilingual_discrepancy`, with both texts, the differing spans, the
    prevailing language and a suggested fix in both languages.
- **VN-specific machine checks** (playbook rules, [05](05-contract-review-workflow.md) §3) `[verify]`:
  - penalty above 8% of the breached obligation in a commercial contract (LTM Điều 301);
  - penalty and damages both claimed without agreeing to both (LTM Điều 307 / BLDS Điều 418);
  - foreign governing law with no foreign element (BLDS Điều 663/683);
  - foreign arbitration or courts without a foreign element;
  - prices or payments in foreign currency between residents (foreign-exchange rules);
  - limitation periods shorter than the law allows;
  - missing signing authority or power of attorney (giấy ủy quyền);
  - personal-data clauses lacking what the PDP Law requires of processing contracts;
  - cross-border data transfer without a transfer dossier or consent language.
- **Outputs:**
  - Redline DOCX with tracked changes in both language columns.
  - Memo in VI, EN or both (a per-matter setting).
  - Citations always in the original Vietnamese, with an optional unofficial English gloss.

## 5. Models and routing
- **Pilot hosting of models (ADR-022):**
  - No GPU on the VPS. T1 open-weight models run through **pay-per-token OpenAI-compatible
    APIs** (e.g. OpenRouter, DeepInfra, Fireworks, Together `[verify]`), using the existing
    router adapter (ADR-009).
  - Prefer providers with no-retention / no-training terms, recorded on the endpoint (`zdr`).
  - Embeddings run on the VPS CPU with a small multilingual model (multilingual-e5 base class
    `[verify]`). The corpus is embedded once in batch; queries are embedded one at a time.
  - Pilot supports text-layer PDFs and DOCX only; OCR comes after the pilot.
- **T1 choice (Q5):** evaluate at least 3 open-weight candidates on Vietnamese and bilingual
  tasks before choosing: classification, extraction, playbook compare, discrepancy detection,
  and law-check answers in Vietnamese. Candidates are strong multilingual families (for example
  Qwen class) and Southeast-Asia-tuned models (SeaLLM, Vistral class) `[verify]`.
- **Router:**
  - The Task Descriptor already carries `languages` ([03](03-model-routing-and-hybrid-inference.md)).
  - Endpoints gain `languages` (with a quality tier) and `region`. Policy prefers endpoints rated
    for `vi`.
  - Residency (§6) is enforced as a hard filter, like conflicts.
- **Prompts:** add `prompts/<task>/v1.vi.md` wherever the model must write Vietnamese. Keep one
  English system prompt for reasoning if evals show it works better.
- **Escalation to T2:** allowed in the pilot for firms that accept the §6 terms. It stays
  switchable per firm and per matter (existing conflict rules). Without it, a low-confidence
  finding goes to `needs_human`, the existing ADR-012 behaviour.

## 6. Data protection, hosting and compliance (pilot posture, ADR-022)
**Where data goes in the pilot:**
- Documents, extracted text, embeddings, findings and logs are on one Contabo VPS, preferably in
  the Singapore location (closest to Vietnam) `[verify]`.
- Model calls go to hosted APIs, which may be in the US or EU.
- This is a **cross-border transfer of personal data** under Vietnam's PDP rules: contracts name
  signatories and contain ID numbers and contact details.

**Safeguards before the first real client document:**
1. **Pilot agreement + DPA (VI/EN)** with each firm. Travo acts as processor. The DPA states the
   hosting location, the model providers and retention.
2. **Cross-border transfer impact assessment dossier:** prepared with counsel. Who files it, the
   firm or Travo, is `[verify]`.
3. **Firm-level switch `allow_offshore_processing`** (router hard filter). It is off until
   items 1–2 are signed. With it off, reviews run only on the T0 rules and a lawyer.
4. **Pilot on low-sensitivity or anonymised matters first.** Firms are asked to redact personal
   identifiers where practical.
5. **Security on a single VPS:**
   - Firewall: only 80/443 and key-only SSH.
   - Postgres is not exposed. The Coolify dashboard is behind an IP allowlist and 2FA.
   - Unattended security updates.
   - `TRAVO_MASTER_KEY` held as a Coolify secret. Documents and BYO keys are already
     envelope-encrypted.
   - Nightly encrypted Postgres + object backups to off-site S3-compatible storage.
   - `TRAVO_ALLOW_DEV_TOKENS=false` and `TRAVO_REQUIRE_VERIFIED_SOURCES=true`.
6. **Model providers:** no-training terms, and zero-retention where available. Each call is
   logged in `routing_decisions` (provider, host, region).

| Topic | Pilot plan | Later |
|---|---|---|
| Hosting | Coolify on one Contabo VPS (§12) | Move the same containers to a VN provider or a second VPS when customers require residency or scale (VN1) |
| PDP Law | DPA, transfer dossier, breach runbook, privacy notice | DPO and processing impact dossiers as volume grows `[verify requirements]` |
| Cybersecurity Law / Decree 53 | Legal opinion before paid launch (depends on entity, VN2) | VN hosting if localisation applies |
| Law on Lawyers | Travo supports lawyers and gives no legal advice. Every finding is dispositioned by a lawyer. | — |
| Entity and tax (VN2) | Pilot is free, so it has no invoicing | Decide before paid conversion |
| AI rules | Track Vietnam's AI and digital-technology legislation (2025–2026) `[verify]` | — |

## 7. UX (Vietnamese)
- `src/i18n/vi.ts` with full coverage. Vietnamese is the default locale for VN tenants, and each
  user can switch. Locale-aware dates (dd/mm/yyyy) and numbers (1.000.000 ₫).
- **Bilingual canvas:**
  - VI and EN side by side with row alignment.
  - Discrepancy markers show the differing spans highlighted in both texts.
  - A "prevailing language" badge.
  - Filtering by discrepancy severity.
  - Keyboard shortcuts as in [08](08-ux-ui-spec.md).
- The sources drawer shows the Vietnamese legal text, pinpointed to Khoản and Điểm, with an
  "unofficial translation" toggle when a licensed translation exists.
- Vietnamese fonts and diacritics are checked in both themes and in DOCX exports.

## 8. Evaluation (release gates, [11](11-evaluation-and-quality.md))
| Set | Size | Built from | Gate |
|---|---|---|---|
| Bilingual NDAs + services contracts (real, annotated) | 30 + 30 | Design partners (anonymised) | Clause F1 ≥ 0.85 |
| Bilingual discrepancy (seeded) | 100 pairs | Real bilingual contracts with injected changes to numbers, dates, negation and obligations | Recall ≥ 0.90, precision ≥ 0.80 |
| Figures vs words amounts | 200 | Generated + real | 100% (deterministic) |
| VN law-check Q&A | 100 | Written by the VN legal engineer from verified sources | Supported-citation rate ≥ 0.95; 0 invented articles |
| Cross-lingual retrieval | 100 queries | English clause → Vietnamese article | Recall@10 ≥ 0.85 |
| VI UI / memo language quality | Rubric | VN lawyers | ≥ 4/5 |

The existing synthetic `vn_bilingual_nda` stays a smoke test only.

## 9. Workstreams and sequence (indicative, from kickoff)
Parallel where possible; about 10–12 weeks to pilot with a team as in [12](12-roadmap.md) plus a
VN legal engineer. The Coolify pilot removes the VN-cell infrastructure from the critical path.

| # | Workstream | Weeks | Depends on | Main code |
|---|---|---|---|---|
| V0 | Decisions and inputs: VN1–VN7 (§10), VN legal engineer, 2–3 design partners, T1 shortlist | 0–2 | Founder | — |
| V1 | VN legal corpus: `vn.yaml`, encoding normalisation, `parsers_vn.py`, vbpl HTML/DOCX, validity relationships, `unaccent` + syllable search, 15 instruments imported and verified — **code done 2026-09-30** (manifest with `url: null`, parser, migration 0008, NFC citations, Vietnamese pinpoints). Content waits for network access to the VN domains (or runs on the VPS) and a lawyer's `legal-verify`; validity relationships not started | 1–6 | Official texts (VN3), lawyer | `travo_rag/sources/*`, migration 0005, `retrieval.py`, `citations.py` |
| V2 | Dense cross-lingual retrieval: pgvector, CPU multilingual embeddings on the VPS, RRF fusion | 2–6 | — | `retrieval.py` (DenseRetriever hook), migration |
| V3 | Bilingual contracts: DOCX table parsing, Khoản/Điểm segmentation, alignment, T0 discrepancy checks (including the figures-vs-words parser), semantic discrepancy task, prevailing language, `bilingual_discrepancy` findings — **done 2026-09-30** (four layouts; findings `kind = bilingual`, ADR-023) | 2–8 | T1 endpoint for the semantic part | `parsing.py`, `segmentation.py`, new `travo_agents/bilingual.py`, `checks.py`, `reviews.py` |
| V4 | VN jurisdiction pack and playbooks: `jurisdiction_packs/vn.yaml`, `playbooks/{nda_vn,commercial_vn,services_vn,dpa_vn}.yaml`, VN machine checks (§4), Vietnamese prompts, lawyer sign-off — **drafts done 2026-09-30**, every legal reference `[verify]`; lawyer sign-off open | 3–8 | V1, VN legal engineer | `config/*`, `travo_agents/checks.py`, `prompts/` |
| V5 | Models and routing: T1 evaluation in Vietnamese on hosted APIs, endpoint `languages`/`region`/`zdr`, `allow_offshore_processing` hard filter — **routing done 2026-09-30** (`default_policy_vn.yaml`, OpenRouter T1 endpoint `[verify]`); T1 evaluation in Vietnamese needs an API key | 2–6 | Q5, API keys | `travo_router/*`, `config/endpoints.yaml`, `default_policy.yaml` |
| V6 | Pilot deployment — **done 2026-09-30:** Dockerfiles (api/worker, web), Coolify compose, production guard, https-only IdPs, backups script, local smoke test, runbook. The VPS already runs Coolify; the deploy itself waits for SSH access. | 1–3 | VPS access | `deploy/`, `scripts/deploy_smoke.py`, `docs/runbooks/deploy-coolify.md` |
| V7 | Vietnamese UX: `vi.ts`, locale formats, bilingual canvas, VI/EN memos, bilingual redline DOCX — **done 2026-09-30** (`TRAVO_DEFAULT_LOCALE=vi` in the pilot) | 4–10 | V3 | `apps/web/src/*`, `exports.py` |
| V8 | Compliance: DPA (VI/EN), impact assessment dossiers, breach runbook, legal opinions (Decree 53, Law on Lawyers), privacy notice | 0–10 | Counsel | `docs/06`, legal |
| V9 | Evals and pilot readiness: VN gold sets (§8), gates in CI, SCIM/rate limits/pen test (from P1), onboarding — **partly done 2026-09-30:** synthetic VN gold set + gates in `make check`/`make eval`, sign-in rate limit, VN e2e and deploy smoke. Real-contract gold set, SCIM, pen test and onboarding open | 6–14 | V1–V7 | `evals/`, CI |

SG/MY: keep the build green. Finish the MY corpus only when inputs arrive; no new SG/MY
features until the VN pilot starts.

## 10. Decisions needed (added to [13](13-open-questions.md))
| # | Question | Default in this plan |
|---|---|---|
| VN1 | Hosting | **Decided: Coolify on a Contabo VPS for the MVP pilot** (ADR-022). VN hosting only when customers require it. |
| VN2 | Entity: VN subsidiary or offshore SaaS? (localisation, tax, invoicing in VND) | Pilot is free; decide before paid conversion, with a legal opinion |
| VN3 | Legal materials | **Decided: scrape official government sites** (§3.1). No commercial databases. |
| VN4 | T1 model for Vietnamese | **Decided: hosted pay-per-token APIs for the pilot.** Choose among 3 candidates by eval. |
| VN5 | Launch contract types | **Decided: NDA, commercial contracts (sale/supply of goods), services, DPA** |
| VN6 | Default UI and memo language | UI in Vietnamese; memo language chosen per matter |
| VN7 | Design-partner firms and the VN legal engineer (hire or contract) | 2–3 firms in HCMC/Hanoi; legal engineer by week 2 |
| VN8 | Offshore processing | Per-firm switch; on only after DPA + transfer dossier (§6) |

## 11. Risks
| Risk | Mitigation |
|---|---|
| Vietnamese law changes often; stale text | Consolidated texts first; validity relationships; monthly refresh; stale warnings; lawyer re-verification (ADR-019) |
| Poor legacy encodings / scanned gazettes | Encoding detection and refusal; vbpl HTML/DOCX first; OCR fallback plus lawyer check |
| Open-weight model weak in Vietnamese legal language | Evaluate before committing; Vietnamese few-shot from firm edits (ADR-015); escalation allowed only with opt-in |
| Offshore pilot hosting challenged by a firm or regulator | §6 safeguards; containers portable to VN hosting; start with low-sensitivity matters |
| Single VPS fails or is compromised | Nightly off-site encrypted backups with a tested restore; hardening checklist; restore drill before the first client document |
| No English authoritative law; lawyers want English | Show Vietnamese source + labelled unofficial gloss; memo in EN with Vietnamese citations |
| Local competitors / legal databases add AI | Bilingual discrepancy + verified citations + VN hosting as the wedge; partner with databases rather than compete |

## 12. Pilot deployment and cost (Coolify on Contabo, ADR-022)
**Topology (one VPS; Coolify manages the containers and TLS via its proxy):**
- `postgres`: `pgvector/pgvector:pg16`, private network only, with a volume.
- `api`: FastAPI/uvicorn. Runs migrations at deploy as the owner role, then serves as `travo_api`.
- `worker`: `travo worker`, the durable review runner.
- `web`: Next.js, standalone build.
- Scheduled jobs:
  - `legal-fetch -j VN` weekly, then report; a human ingests and verifies.
  - Nightly encrypted backups (Postgres dump + object store) to S3-compatible off-site storage.
- Storage: the object store stays on the local filesystem (`TRAVO_STORAGE_DIR` on a volume),
  envelope-encrypted as today.

**Sizing (start):** one VPS with about 6–8 vCPU, 16–24 GB RAM and NVMe. That is enough for
Postgres, API, worker, web, and CPU embeddings for a pilot of 2–3 firms. Scale vertically first.

**Monthly cost (estimates, 2026-09-30, `[verify]` prices):**

| Item | Estimate |
|---|---|
| Contabo VPS (Singapore) | ≈ €15–30 |
| Off-site backup storage | ≈ €3–5 |
| Domain + email | ≈ €2 |
| Model APIs (T1 open-weight, pay-per-token) | Usage-based. A bilingual 10–15 page contract is about 100–200k tokens across all steps, so roughly US$0.02–0.20 per review at open-weight prices. T2 escalations cost more. |
| Coolify | Self-hosted, free |

**Deployment work (V6):**
- `deploy/Dockerfile.api` (also used by the worker) and `deploy/Dockerfile.web`.
- `deploy/docker-compose.coolify.yml`.
- Healthchecks: `/healthz` for the API, `/` for the web.
- An `.env` template listing required secrets. The app refuses to start if
  `TRAVO_ALLOW_DEV_TOKENS=true` without a dev flag.
- `docs/runbooks/deploy-coolify.md`: first install, hardening, backups and restore drill,
  upgrades, rollback.

## 13. Release status (2026-09-30)

The source is **release-ready for the pilot** in the sense of the release plan: a lawyer can sign
in (SSO) to a Vietnamese UI and review a Vietnamese-only, English-only or bilingual NDA, sale,
services or DPA contract. The review includes clause pairing, VI–EN discrepancy findings, draft
VN playbooks and VI/EN/both redlines and memos. Gates passed: `make check`, `make web-check`,
`make e2e` (including the Vietnamese flow), `make eval` (VN gates) and `make deploy-smoke`
(including a bilingual review by the worker).

What the pilot does **not** have yet, by design:
- **No verified VN legal corpus.** Law findings say "needs lawyer" until instruments are fetched
  (`legal-fetch -j VN` on the VPS), ingested and `legal-verify`-ed.
- **Draft playbooks** (`[verify]` throughout) until a Vietnamese-qualified lawyer signs them off.
- **Synthetic evals only.** The VN gold set is generated (`evals/vn_gold.py`); a set of real,
  consented contracts is needed before quality claims.
- **No DPA or transfer dossier.** Until §6 is complete, `allow_offshore_processing` stays
  false and no real client documents are used; T0 rules still run.

