# 06 — Security, Compliance & Ethical Walls

> **Status:** Draft v1 · **Last updated:** 2026-09-29 · **Related:** [02](02-system-architecture.md), [03](03-model-routing-and-hybrid-inference.md), [09](09-data-model-and-apis.md)
>
> Legal references are summaries for engineering purposes, not legal advice. Validate with local counsel `[verify]`.

## 1. Threat model (top risks)
| Risk | Mitigation |
|---|---|
| Cross-tenant data leakage | Postgres RLS on `tenant_id`; per-tenant KMS keys; per-tenant vector namespaces; tenant-scoped service tokens; automated cross-tenant access tests in CI. |
| Leakage across an ethical wall inside a firm | Matter-level ACLs enforced in API, retrieval, agents' tool calls, telemetry and datasets (see §3). |
| Model provider retains/trains on data | Zero-data-retention agreements; BYO-key mode; open-weight self-hosting; router blocks non-compliant endpoints. |
| Conflict-of-interest via provider | Per-matter provider deny lists enforced by router (see [03](03-model-routing-and-hybrid-inference.md)). |
| Prompt injection from uploaded documents | Documents treated as untrusted data; tool permissions scoped per agent; no outbound network tools for document-reading agents; output validators; injection classifiers on ingest. |
| Hallucinated legal advice | Per-claim validation + export gate ([04](04-legal-rag-and-citation-validation.md)). |
| Insider access at Travo | No standing production access; break-glass with customer-visible audit; support access requires tenant admin approval. |
| Data residency breach | Region cells; router residency filter; no cross-cell replication by default. |

## 2. Isolation model
```
Tenant (law firm)  ── KMS key, DB RLS, vector namespace root, object-store prefix
 └─ Client          ── optional client-level AI policy (allowed providers)
     └─ Matter      ── ethical wall (members), conflict profile, residency, budget
         └─ Document / Clause / Finding / Citation / Correction / RoutingDecision
```
- Encryption: AES-256 at rest with tenant keys (BYOK/HYOK for enterprise via customer-managed KMS), TLS 1.3 in transit.
- Embeddings are treated as sensitive (they can leak content) — same isolation as documents.
- Firm-private datasets and LoRA adapters are tenant-scoped artifacts; never mixed across tenants without explicit written opt-in.

## 3. Ethical walls
- **Wall definition:** matter membership list (users/groups) + optional "screened" list (explicitly excluded).
- **Enforcement points:**
  1. API authorisation (every request checks membership).
  2. Retrieval filter (matter namespace + ACL metadata) — excluded users' agents cannot retrieve.
  3. Firm-knowledge retrieval excludes documents from matters the user is screened from, even if tagged as precedents.
  4. Telemetry and flywheel datasets inherit matter ACL; training on walled-matter data requires KM/risk approval.
  5. Search, notifications and activity feeds filtered identically.
- **Integration:** import walls from firm systems (Intapp Walls, iManage/NetDocuments security) via connectors (P2).
- **Audit:** every access and denied access logged; exportable report per matter.

## 4. Compliance controls
- Append-only audit log (who, what, when, which model, which sources, which overrides).
- Legal hold and retention policies per matter; secure deletion (crypto-shred tenant keys on offboarding).
- DLP/PII detection on ingest; optional pseudonymisation before frontier escalation.
- Admin console: provider policy, residency, retention, wall management, spend limits.

## 5. ASEAN data-protection mapping
| Law | Key obligations relevant to Travo | Design response |
|---|---|---|
| **Singapore PDPA 2012** (as amended 2020) | Consent/purpose limitation, protection obligation, transfer limitation (comparable protection), 3-day breach notification to PDPC once assessed notifiable | SG region default; DPA with firms; provider DPAs; breach runbook. |
| **Malaysia PDPA 2010** (Amendment Act 2024) | Data processors directly liable for security principle; mandatory breach notification; DPO appointment; cross-border transfer relaxed to adequacy/other conditions | Processor security controls; DPO; breach notification flow; transfer assessments. |
| **Vietnam Decree 13/2023/ND-CP** and **Law on Personal Data Protection (2025, effective 2026)** | Impact assessment dossiers for processing and for cross-border transfer, filed with the Ministry of Public Security (A05); data-subject consent; breach notification within 72h | VN-local cell option; generate PDPIA / transfer impact assessment templates; consent records; router residency filter. |
| **Vietnam Cybersecurity Law 2018 / Decree 53/2022** | Data localisation obligations for certain domestic service providers upon request | VN cell architecture ready; legal review of applicability. |
| **Indonesia PDP Law 27/2022** (fully effective Oct 2024) | Controller/processor duties, DPIA for high-risk processing, cross-border transfer conditions, 3×24h breach notification | Jakarta cell option; DPIA templates; transfer safeguards. |
| **Professional rules** (SG Legal Profession Act & PCR, Bar Council MY, VN Law on Lawyers, ID Advocates Law) | Client confidentiality, supervision duty, competence | Human-in-the-loop, export gate, supervision records, confidentiality architecture. |

## 6. Certification path
| When | Target |
|---|---|
| P1 | Security baseline: SSO, MFA, RLS, KMS, pen test #1, policies |
| P2 | SOC 2 Type I, ISO/IEC 27001 gap assessment, SG MTCS/CSA Cyber Trust mark `[verify]` |
| P3 | SOC 2 Type II, ISO 27001 certified, ISO/IEC 42001 (AI management) readiness |
| P4 | ISO 42001, customer-specific audits, on-prem deployment hardening guide |

## 7. As built — sign-in, sessions and browser security (2026-09-29, ADR-018)
- **Per-firm SSO (OIDC).** Authorization code + PKCE (S256). The API does discovery, the code
  exchange (client secrets stay in the API, encrypted with the firm's key) and id_token
  validation: signature via JWKS (rotation-aware), `iss`, `aud`/`azp`, `exp`/`iat` (60 s leeway),
  `nonce`, `email_verified`. State is checked by the web BFF. Failures return a generic
  "sign-in failed"; the reason goes to the audit log (`auth.login_failed`).
- **No JIT provisioning.** Users must exist; first sign-in binds the IdP subject, later sign-ins
  must match it (an email re-assigned to another IdP identity is refused).
- **One firm per email domain**, enforced by a global primary key. Domain ownership
  verification (DNS TXT) is a pre-GA item `[verify]`.
- **Sessions are server-side and revocable** (`auth_sessions`, 8 h). Users can sign out; admins
  can revoke any session. Tokens without a session (dev tokens) are refused when
  `TRAVO_ALLOW_DEV_TOKENS=false`, which is mandatory wherever client data lives.
- **Browser never holds a bearer token.** The Next.js BFF keeps it in an httpOnly, SameSite=Lax
  (Secure in production) cookie and adds it server-side on `/api/*`.
- **CSRF:** writes through the BFF need `X-Travo-CSRF: 1` and a same-origin `Origin`.
- **CSP:** per-request nonce, `script-src 'self' 'nonce-…' 'strict-dynamic'` (no `unsafe-eval` in
  production), `frame-ancestors 'none'`, `form-action 'self'`, `object-src 'none'`; plus
  `X-Frame-Options`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`.
  `style-src` still allows inline styles (React style attributes).
- **Cross-tenant lookups at sign-in** go only through `idp_for_email_domain()` / `idp_by_id()`
  (SECURITY DEFINER, role `travo_idp_lookup`), which return ids and public IdP coordinates.
- Not yet: SCIM provisioning, MFA policy enforcement beyond the IdP, rate limiting on
  `/v1/auth/*`, IdP-initiated logout.
