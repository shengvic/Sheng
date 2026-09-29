# 09 — Data Model & APIs

> **Status:** Draft v1 · **Last updated:** 2026-09-29 · **Related:** [02](02-system-architecture.md), [06](06-security-compliance-ethical-walls.md)

## 1. Core entities
All tables include `tenant_id` (RLS key), `created_at`, `updated_at`, `created_by`. Matter-scoped tables also include `matter_id`.

| Entity | Key fields |
|---|---|
| `Tenant` | name, region_cell, billing_mode, kms_key_ref, settings |
| `User` | email, role (partner/associate/km/admin), practice_groups, locale |
| `Client` | name, ai_policy (allowed/denied providers, training_allowed) |
| `Matter` | client_id, number, name, jurisdictions[], residency, conflict_profile{deny_providers[]}, budget_usd, status |
| `MatterMember` | matter_id, user_id/group_id, access (member/screened) |
| `Document` | matter_id, filename, mime, storage_ref, language[], type, governing_law, parties[], signing_date, parse_status, version |
| `Clause` | document_id, taxonomy_key, text, span{start,end}, language, parallel_clause_id |
| `Playbook` | key, version, applies_to, clauses[] (JSON), status (draft/active), owner |
| `ReviewRun` | matter_id, document_id, playbook_id@version, workflow_id, status, cost_usd, started/finished |
| `Finding` | review_run_id, clause_id, playbook_rule_key, classification (standard/fallback/non_standard/missing), severity, summary, suggested_redline, confidence, model_tier, disposition, disposition_by |
| `Citation` | finding_id / memo_id, claim_text, source_id, pinpoint, status (supported/partial/contradicted/not_found), checker_model, override_reason |
| `LegalSource` | jurisdiction, instrument_type, number, title, unit_path, text, language, effective_from/to, status, version_hash, url (shared, no tenant) |
| `Correction` | finding_id, action, before, after, reason_code, note, user_role, time_spent_ms |
| `RoutingDecision` | task_descriptor (JSON), candidates, filtered (with reasons), chosen_endpoint, tier, escalated_from, tokens_in/out, cost_usd, latency_ms, outcome |
| `ProviderCredential` | tenant_id, provider, encrypted_key_ref, status, last_tested |
| `ModelPolicy` | tenant_id, version, yaml, active |
| `Adapter` | tenant_id, base_model, version, dataset_version, eval_report_ref, status (shadow/canary/active/retired) |
| `AuditEvent` | actor, action, resource, matter_id, ip, result, details (append-only, WORM storage) |

## 2. API (REST, JSON; OpenAPI in `packages/schemas` once code starts)
```
POST   /v1/matters                         create matter (+ conflict profile, residency)
GET    /v1/matters/{id}
PUT    /v1/matters/{id}/members            ethical-wall membership
POST   /v1/matters/{id}/documents          upload (multipart) → Document
GET    /v1/documents/{id}                  metadata + parse status
POST   /v1/documents/{id}/reviews          start ReviewRun {playbook_id?}
GET    /v1/reviews/{id}                    status, progress, cost
GET    /v1/reviews/{id}/findings           list, filters
PATCH  /v1/findings/{id}                   disposition {action, edited_text?, reason_code?, note?}
GET    /v1/findings/{id}/citations
POST   /v1/reviews/{id}/export             {format: docx_redline|memo_docx|xlsx} → export gate check
GET    /v1/playbooks  POST /v1/playbooks  PUT /v1/playbooks/{key}  (versioned)
POST   /v1/playbooks/{key}/test            run against sample docs
GET    /v1/admin/model-policy  PUT /v1/admin/model-policy  POST /v1/admin/model-policy/dry-run
POST   /v1/admin/provider-credentials      BYO key (write-only)
GET    /v1/admin/routing-decisions         filters: matter, provider, date
GET    /v1/admin/audit                     search/export
GET    /v1/insights/learning               "Travo is learning" digest
```
- Streaming progress: Server-Sent Events `GET /v1/reviews/{id}/events`.
- Webhooks (P2): `review.completed`, `export.created` for DMS integrations.

## 3. Internal contracts
- **Router API** (OpenAI-compatible chat/completions + `x-travo-task` header carrying the Task Descriptor). Returns `x-travo-routing-decision-id`.
- **Retrieval API:** `POST /retrieve {query, jurisdictions, as_of_date, scopes:[legal, firm, matter], matter_id, k}` → evidence pack.
- **Validator API:** `POST /validate {text_with_cites, evidence_pack_id}` → claims with verdicts.
- **Events** (Kafka/NATS or Postgres outbox → queue): `document.uploaded`, `review.step.completed`, `finding.dispositioned`, `routing.decision`, `escalation.completed`.
