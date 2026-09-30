# 14 — Vietnam-First Launch Plan

> **Status:** Draft v1 · **Last updated:** 2026-09-30 · **Related:** ADR-021, [01](01-product-vision-and-prd.md), [04](04-legal-rag-and-citation-validation.md), [05](05-contract-review-workflow.md), [06](06-security-compliance-ethical-walls.md), [08](08-ux-ui-spec.md), [11](11-evaluation-and-quality.md), [12](12-roadmap.md), [13](13-open-questions.md)
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
| Hosting | SG cell | **VN residency by default** for client documents; offshore processing only as an explicit firm opt-in (§6) |
| UI | English | **Vietnamese UI**, English as an option; memos in VI or EN |
| Models | English quality | Vietnamese and bilingual quality decide the T1 choice |

## 2. Launch scope (Vietnam MVP)
**Users:** Vietnamese law firms in HCMC and Hanoi that do foreign-investment and commercial work,
and the Vietnam offices of regional firms. Personas as in [01](01-product-vision-and-prd.md): associate,
partner, KM/legal-ops, IT/admin.

**Contract types (default, confirm with design partners — VN5):**
1. NDA / confidentiality agreement (bilingual and VI-only)
2. Commercial services / supply agreement (hợp đồng dịch vụ / mua bán hàng hóa)
3. Data processing agreement under the PDP Law (hợp đồng xử lý dữ liệu cá nhân)

Later: distribution/agency, labour contracts and NDAs with employees (Bộ luật Lao động),
leases, M&A/SPA.

**Launch-critical features:**
- Review of bilingual contracts: clause alignment, **discrepancy detection**, and which language
  prevails.
- Vietnamese law checks grounded in verified Vietnamese sources, with per-claim citations in
  Vietnamese citation style (`Khoản 1 Điều 301 Luật Thương mại 2005`).
- Vietnamese playbooks, a Vietnamese UI, and memos and redlines in VI, EN or both.
- Client documents stored and processed in Vietnam by default.

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
| Commercial databases (Thư Viện Pháp Luật, LuatVietnam) | English translations and annotations | Only under licence (Q2). Translations are always labelled "unofficial translation". |

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
- **Escalation to T2:** frontier models run offshore, so escalation of VN matters is **off by
  default**. It is allowed per firm only with the opt-in in §6. Without it, a low-confidence
  finding goes to `needs_human`, the existing ADR-012 behaviour.

## 6. Data residency, hosting and compliance
**Default posture (ADR-021):**
- Client documents, derived text, embeddings, findings and logs of VN tenants are stored and
  processed in a **VN cell**.
- T1 inference runs in Vietnam.
- Anything that leaves Vietnam goes through the router under a firm-level switch
  `allow_offshore_processing`. That switch requires the firm's confirmation that consent and
  the cross-border transfer dossier are in place.
- Every offshore call is logged in `routing_decisions`.

| Topic | Plan | Owner |
|---|---|---|
| VN cell | Same stack as the SG cell (Terraform) on a VN cloud with GPUs: Viettel IDC, FPT Smart Cloud, VNG Cloud or CMC `[verify]` (Q4/VN1) | Eng |
| Interim | Until the VN cell exists, pilot data stays in the SG cell only with the firm's written acceptance and a cross-border transfer dossier. Otherwise the pilot waits. | Founder + counsel |
| PDP Law | Travo acts as the firm's **processor**: a DPA template, the processing impact assessment dossier, cross-border transfer dossiers where relevant, breach notification runbook, DPO contact `[verify requirements]` | Compliance |
| Cybersecurity Law / Decree 53 | Legal opinion on whether localisation applies to Travo (depends on entity and service type, VN2) | Counsel |
| Law on Lawyers / professional rules | Travo supports lawyers and does not give legal advice. Every finding is dispositioned by a lawyer, and client confidentiality is covered in the DPA. | Product + counsel |
| Entity and tax (Q9/VN2) | VN subsidiary vs offshore SaaS affects localisation, foreign contractor tax, VND invoicing and trust | Founder |
| AI rules | Track Vietnam's AI and digital-technology legislation (2025–2026) `[verify]` | Compliance |

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
Parallel where possible; about 12–14 weeks to pilot with a team as in [12](12-roadmap.md) plus a
VN legal engineer.

| # | Workstream | Weeks | Depends on | Main code |
|---|---|---|---|---|
| V0 | Decisions and inputs: VN1–VN7 (§10), VN legal engineer, 2–3 design partners, T1 shortlist | 0–2 | Founder | — |
| V1 | VN legal corpus: `vn.yaml`, encoding normalisation, `parsers_vn.py`, vbpl HTML/DOCX, validity relationships, `unaccent` + syllable search, 15 instruments imported and verified | 1–6 | Official texts (VN3), lawyer | `travo_rag/sources/*`, migration 0005, `retrieval.py`, `citations.py` |
| V2 | Dense cross-lingual retrieval: pgvector, multilingual embeddings as T0 (in VN), RRF fusion | 2–6 | Embedding host in VN | `retrieval.py` (DenseRetriever hook), migration |
| V3 | Bilingual contracts: DOCX table parsing, Khoản/Điểm segmentation, alignment, T0 discrepancy checks (including the figures-vs-words parser), semantic discrepancy task, prevailing language, `bilingual_discrepancy` findings | 2–8 | T1 endpoint for the semantic part | `parsing.py`, `segmentation.py`, new `travo_agents/bilingual.py`, `checks.py`, `reviews.py` |
| V4 | VN jurisdiction pack and playbooks: `jurisdiction_packs/vn.yaml`, `playbooks/{nda_vn,services_vn,dpa_vn}.yaml`, VN machine checks (§4), Vietnamese prompts, lawyer sign-off | 3–8 | V1, VN legal engineer | `config/*`, `travo_agents/checks.py`, `prompts/` |
| V5 | Models and routing: T1 evaluation in Vietnamese, endpoint `languages`/`region`, residency hard filter, `allow_offshore_processing`, VN-default escalation off | 2–7 | Q5, VN1 | `travo_router/*`, `config/endpoints.yaml`, `default_policy.yaml` |
| V6 | VN cell: Terraform for a VN cloud, KMS, backups, GPU inference (vLLM), OCR in-region; SG interim path | 4–10 | VN1 provider contract | `infra/` (new) |
| V7 | Vietnamese UX: `vi.ts`, locale formats, bilingual canvas, VI/EN memos, bilingual redline DOCX | 4–10 | V3 | `apps/web/src/*`, `exports.py` |
| V8 | Compliance: DPA (VI/EN), impact assessment dossiers, breach runbook, legal opinions (Decree 53, Law on Lawyers), privacy notice | 0–10 | Counsel | `docs/06`, legal |
| V9 | Evals and pilot readiness: VN gold sets (§8), gates in CI, SCIM/rate limits/pen test (from P1), onboarding | 6–14 | V1–V7 | `evals/`, CI |

SG/MY: keep the build green. Finish the MY corpus only when inputs arrive; no new SG/MY
features until the VN pilot starts.

## 10. Decisions needed (added to [13](13-open-questions.md))
| # | Question | Default in this plan |
|---|---|---|
| VN1 | VN hosting provider for the VN cell (GPU availability, certifications, price) | Shortlist Viettel IDC / FPT Smart Cloud / VNG Cloud; decide by week 2 |
| VN2 | Entity: VN subsidiary or offshore SaaS? (localisation, tax, invoicing in VND) | Obtain a legal opinion; assume a VN entity for the pilot |
| VN3 | Terms of re-use for vbpl.vn / Công báo text; licence for English translations (Thư Viện Pháp Luật / LuatVietnam) | Official Vietnamese text only; no English translations at launch |
| VN4 | T1 model for Vietnamese, and where it runs (VN GPUs vs SG) | Evaluate 3; host in VN |
| VN5 | Launch contract types | NDA, commercial services/supply, DPA |
| VN6 | Default UI and memo language | UI in Vietnamese; memo language chosen per matter |
| VN7 | Design-partner firms and the VN legal engineer (hire or contract) | 2–3 firms in HCMC/Hanoi; legal engineer by week 2 |
| VN8 | Offshore processing policy for pilots (frontier escalation, SG interim hosting) | Off by default; per-firm opt-in with a transfer dossier |

## 11. Risks
| Risk | Mitigation |
|---|---|
| Vietnamese law changes often; stale text | Consolidated texts first; validity relationships; monthly refresh; stale warnings; lawyer re-verification (ADR-019) |
| Poor legacy encodings / scanned gazettes | Encoding detection and refusal; vbpl HTML/DOCX first; OCR fallback plus lawyer check |
| Open-weight model weak in Vietnamese legal language | Evaluate before committing; Vietnamese few-shot from firm edits (ADR-015); escalation allowed only with opt-in |
| Residency rules block the SG cell | VN cell in the critical path from week 4; interim only with a signed dossier |
| No English authoritative law; lawyers want English | Show Vietnamese source + labelled unofficial gloss; memo in EN with Vietnamese citations |
| Local competitors / legal databases add AI | Bilingual discrepancy + verified citations + VN hosting as the wedge; partner with databases rather than compete |
