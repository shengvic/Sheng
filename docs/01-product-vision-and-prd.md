# 01 — Product Vision & PRD

> **Status:** Draft v1 · **Last updated:** 2026-09-29 · **Related:** [00](00-competitive-analysis.md), [05 Workflow](05-contract-review-workflow.md), [12 Roadmap](12-roadmap.md)

## 1. Vision
Travo is the **agentic legal process enabler for Asia**: a digital senior
associate that executes legal workflows end-to-end under the supervision of the
firm's lawyers, grounded in local law, isolated per client matter, and neutral
across AI model providers.

## 2. Target customers
- **Primary (MVP):** mid-to-large law firms (20–500 lawyers) in Singapore and Malaysia; corporate/commercial, M&A, banking & finance practices.
- **Update 2026-09-30 (ADR-021):** Vietnam is the launch market: Vietnamese firms doing FDI/commercial work are the primary segment; see [14](14-vietnam-launch-plan.md).
- **Secondary (P2, original plan):** Vietnamese and Indonesian firms and the ASEAN offices of international firms handling VN/ID matters.
- **Later:** in-house legal teams of regional corporates.

## 3. Personas & jobs to be done
| Persona | Job to be done | Pain today |
|---|---|---|
| Partner | "Get a reliable first-pass review so I spend time on judgement, not reading." | Associates slow; quality varies; write-offs. |
| Senior associate | "Review 40 supplier agreements against our playbook by Friday." | Repetitive clause checking; cross-referencing local law. |
| Junior associate | "Draft the issues list and redlines, and learn why." | Unsure of firm positions; no feedback loop. |
| KM / practice support lawyer | "Encode our positions and keep them current." | Playbooks live in Word docs nobody reads. |
| IT / risk / GC of the firm | "Adopt AI without breaching confidentiality, ethical walls or client AI restrictions." | Vendor lock-in; clients forbid specific AI providers; data residency. |

## 4. MVP scope — Contract & Agreement Review
**In scope (P1):**
1. Upload one or many contracts (DOCX, PDF incl. scanned via OCR) into a *Matter*.
2. Auto-classify type (NDA, MSA, SPA, SHA, loan/facility, lease, employment, distribution, SaaS/DPA) and governing law/jurisdiction.
3. Route to the right **playbook** (firm template) and **jurisdiction pack** (SG/MY first).
4. Clause extraction and normalisation to a clause taxonomy.
5. Risk findings vs playbook positions (standard / fallback / unacceptable) with severity.
6. Legal checks against local law (e.g., enforceability of penalty clauses, governing-law/jurisdiction, data-protection clauses) with **per-claim citations**.
7. Suggested redlines (tracked changes) and issues list / review memo export (DOCX).
8. Human review: accept / edit / reject each finding with reason codes → telemetry.
9. Admin: model policy per matter, ethical-wall membership, audit log.

**Out of scope for MVP:** litigation research, e-discovery, drafting from scratch, billing integration, client portal.

## 5. Differentiating requirements (non-negotiable)
| ID | Requirement | Spec |
|---|---|---|
| R1 | Legal-specific workflows, template routing, compliance controls | [05](05-contract-review-workflow.md) |
| R2 | Enterprise data isolation, ethical walls | [06](06-security-compliance-ethical-walls.md) |
| R3 | Deep RAG + per-claim citation validation | [04](04-legal-rag-and-citation-validation.md) |
| R4 | In-house HITL data flywheel | [07](07-hitl-telemetry-data-flywheel.md) |
| R5 | Neutral, conflict-aware multi-model router; BYO keys or Travo proxy | [03](03-model-routing-and-hybrid-inference.md) |
| R6 | Hybrid open-weight + frontier with agent-in-the-loop escalation | [03](03-model-routing-and-hybrid-inference.md) |
| R7 | Professional UX with visible self-adaptive improvement | [08](08-ux-ui-spec.md) |

## 6. Success metrics
**Product (per design partner, by end of P1):**
- ≥ 50% reduction in time-to-first-review for standard contracts (measured vs baseline timesheets).
- Finding acceptance rate ≥ 70% (accepted or accepted-with-edit).
- Citation precision ≥ 95%; unsupported-claim rate in final output = 0 (blocked by validator).
- Clause extraction recall ≥ 95% on golden set.

**Business (by end of P2):** 3 paying firms, ≥ 150 paid seats, gross margin ≥ 60% on inference (driven by open-weight routing).

**Platform:** p50 review time for a 30-page contract ≤ 4 min; frontier-escalation share ≤ 25% of tokens.

## 7. Pricing model (hypothesis)
| Plan | Includes | Model access |
|---|---|---|
| **Seat** (per lawyer / month) | Workspace, playbooks, Word add-in, audit | — |
| **BYO Keys** | Firm connects its own OpenAI/Anthropic/Google/Azure/Bedrock keys; Travo charges platform fee only | Firm pays providers directly |
| **Travo Tokens** | Prepaid credits via Travo's proxy (OpenRouter-compatible gateway + Travo-hosted open-weight models) | Transparent per-task cost + margin |
| **Private Deployment** (P4) | Dedicated VPC / on-prem inference | Self-hosted open-weight models |

Blended pricing: seat fee + usage. Travo shows cost per review in the UI.

## 8. Assumptions & risks
- Access to licensed legal databases in MY/SG (CLJ, LexisNexis, LawNet) requires partnerships — see [13](13-open-questions.md).
- Firms will share correction data with Travo only under firm-private terms — flywheel defaults to tenant-private.
- Open-weight models (Qwen, Llama, Mistral, Gemma, DeepSeek families) are good enough for extraction and first-pass review after post-training; frontier stays for complex reasoning.
