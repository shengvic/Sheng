# 00 — Competitive Analysis: Harvey, Legora → Travo

> **Status:** Draft v1 · **Last updated:** 2026-09-29 · **Related:** [01 PRD](01-product-vision-and-prd.md), [03 Routing](03-model-routing-and-hybrid-inference.md)
>
> Competitor facts are from public information up to mid-2026. Items marked `[verify]` should be re-checked before external use.

## 1. Harvey (harvey.ai)

| Dimension | Observation |
|---|---|
| Positioning | "Professional-class AI" for elite law firms and in-house teams; brand built on BigLaw logos (A&O Shearman, PwC Legal, etc.). |
| Product | Assistant (chat + drafting over documents), Vault (bulk document projects, tabular review), Workflows / agents (pre-built multi-step legal tasks), Knowledge (research over legal sources), Word add-in. |
| Models | Historically deep OpenAI partnership (custom-trained case-law model); since 2025 moved to multi-model (added Anthropic and Google models) `[verify]`. |
| Grounding | Partnership with LexisNexis for US primary law and citations `[verify]`; strongest in US/UK common law. |
| Security | SOC 2 Type II, ISO 27001, zero data retention with model providers, per-customer isolation. |
| Go-to-market | Top-down enterprise, high ACV, long pilots; limited ASEAN depth; English-first. |
| Weaknesses for ASEAN | Little Vietnamese/Bahasa content, no civil-law (VN/ID) primary-law grounding, pricing tuned to US/UK BigLaw, no local data residency options in VN/ID. |

## 2. Legora (formerly Leya)

| Dimension | Observation |
|---|---|
| Positioning | Collaborative AI workspace for lawyers; European origin (Stockholm), fast expansion into UK/US and APAC `[verify]`. |
| Product | Tabular review ("Tabular" grid over hundreds of documents), Word add-in, drafting/review assistant, agentic workflows, firm-built custom workflows, strong collaboration UX. |
| Models | Model-agnostic in practice; uses several frontier providers. |
| Grounding | Firm knowledge + public legal sources per jurisdiction; strong multi-lingual (Nordic/European) handling. |
| Differentiator | UX and speed of iteration; lets firms build their own workflows/playbooks; tight Word integration. |
| Weaknesses for ASEAN | Local primary-law corpora and language coverage still thin; no specific VN/ID compliance story; generalized routing without explicit conflict-aware provider policy. |

## 3. Feature matrix

| Capability | Harvey | Legora | **Travo (target)** |
|---|---|---|---|
| Contract review w/ firm playbooks | ✅ | ✅ | ✅ MVP wedge, playbooks per jurisdiction |
| Tabular bulk review | ✅ Vault | ✅ Tabular | ✅ P2 |
| Word add-in | ✅ | ✅ | ✅ P2 |
| Per-claim citation validation (blocking) | Partial (citations shown) | Partial | ✅ Core — unsupported claims flagged or blocked |
| VN / ID civil-law primary sources | ❌ | ❌ | ✅ |
| Vietnamese / Bahasa Indonesia / Malay | Limited | Limited | ✅ native, bilingual contracts |
| Conflict-aware model routing | ❌ | ❌ | ✅ per-matter provider blocklists |
| BYO model API keys | ❌ | ❌ `[verify]` | ✅ |
| Open-weight domain models / on-prem option | ❌ | ❌ | ✅ P3–P4 |
| Firm-private learning from expert corrections | Limited | Limited | ✅ flywheel, per-firm adapters |
| Ethical walls enforced in retrieval & routing | Workspace-level | Workspace-level | ✅ matter-level in retrieval, prompts, logs |
| Regional data residency (SG, VN) | SG via cloud `[verify]` | EU/US | ✅ SG default, VN-local option |
| Price point for mid-size ASEAN firms | High | Mid-high | Mid; usage-transparent |

## 4. What to copy, what to beat

**Copy (table stakes):** Word add-in, tabular review, polished review canvas,
SOC 2/ISO path, zero-retention provider agreements, pre-built workflows.

**Beat on:**
1. **Local law depth** — VN, ID, MY, SG statutes, decrees, circulars, case law, plus bilingual contracts (EN–VI, EN–ID, EN–MS).
2. **Trust** — per-claim validation, not just "citations shown"; a claim without evidence cannot be marked final.
3. **Neutrality** — a router that lets the firm choose (or forbid) providers per matter, and BYO keys. This addresses the *conflict risk* of a firm representing one AI lab against another.
4. **Cost structure** — long, token-heavy jobs run on open-weight models; frontier only on escalation. Enables mid-size-firm pricing.
5. **Firm-specific learning** — corrections by the firm's own senior lawyers become that firm's private advantage, not a shared vendor model.

## 5. Market notes (ASEAN)

| Market | Legal system | Language | Notes |
|---|---|---|---|
| Singapore | Common law | English | Most mature buyer; regional HQ for international firms; MinLaw/SAL legal-tech grants (e.g., LIFT) `[verify]`. Best design-partner market. |
| Malaysia | Common law (+ Syariah) | English / Malay | Strong English-language practice; large domestic firms; cost-sensitive. |
| Vietnam | Civil law | Vietnamese | Contracts often bilingual; heavy reliance on decrees/circulars; data localisation and cross-border transfer rules (Decree 13/2023, PDPL 2025). |
| Indonesia | Civil law | Bahasa Indonesia | Language Law requires Indonesian-language contracts with Indonesian parties; PDP Law 27/2022 in force Oct 2024. |

## 6. Positioning statement
> For law firms across Southeast Asia that need AI they can trust with client
> files, **Travo** is the neutral, locally grounded digital senior associate
> that reviews contracts against your playbooks and local law, proves every
> claim with a citation, runs on the models *you* are allowed to use, and gets
> better from your own lawyers' corrections — unlike Harvey or Legora, which are
> built for US/European practice and a fixed set of model vendors.
