# 11 — Evaluation & Quality

> **Status:** Draft v1 · **Last updated:** 2026-09-30 · **Related:** [04](04-legal-rag-and-citation-validation.md), [07](07-hitl-telemetry-data-flywheel.md)

## 1. Eval sets
| Set | Content | Owner | Size (P1 target) |
|---|---|---|---|
| **Clause extraction gold** | Annotated contracts per type × jurisdiction × language | Travo legal team + design partners | 200 contracts |
| **Playbook compare gold** | Clause ↔ playbook position labels with severity | Design-partner expert reviewers | 1,500 clause labels |
| **Legal QA gold** | Jurisdiction questions with correct pinpoint sources | Local counsel partners | 300 Q/A per jurisdiction |
| **Citation adversarial** | Fake/repealed/misattributed citations the validator must catch | Travo | 300 items |
| **Bilingual discrepancy** | EN–VI / EN–ID / EN–MS pairs with seeded inconsistencies | Travo | 100 pairs |
| **Prompt-injection** | Contracts with hidden instructions | Travo security | 100 docs |
| **Firm golden set** | Per tenant, from expert reviewers ([07](07-hitl-telemetry-data-flywheel.md)) | Firm KM | grows continuously |

## 2. Metrics
- Extraction: precision/recall/F1 per clause key; key-term exact match.
- Compare: accuracy, severity-weighted F1, missed-issue rate (most important).
- Citations: existence accuracy, precision, validator recall on adversarial set.
- Generation: redline acceptance (online), edit distance, LLM-judge rubric with human calibration.
- Operations: latency p50/p95, cost per document, T2 escalation share, failure rate.

## 3. Release gates (CI + pre-promotion)
| Change type | Gate |
|---|---|
| Prompt / agent change | No regression > 1 pt on affected sets; citation existence = 100%; injection suite pass |
| Model / routing-table change | Same + cost/latency within budget |
| Firm adapter promotion | ≥ +2 pts on firm golden set, no regression on global safety/citation sets, shadow run ≥ 1 week |
| Jurisdiction pack update | Local counsel sign-off on changed rules + legal QA gold pass |
| Vietnam pilot (any change) | VN synthetic set (`evals/vn_gold.py`, 4 contract types × 2 layouts × clean/seeded): clause accuracy ≥ 0.9, classification 1.0, discrepancy recall ≥ 0.9 and precision ≥ 0.8, figures-vs-words recall 1.0, playbook findings ≥ 0.9. Enforced by `make eval` and `tests/test_vn_evals.py` |

## 4. Online monitoring
Acceptance rate per task/tier/adapter, override rate on ❌ citations, escalation rate, user-reported errors → triaged weekly; each confirmed error becomes an eval item.
