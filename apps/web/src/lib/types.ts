// Mirrors services/api/travo_api/schemas.py (docs/09). Keep in sync until packages/schemas lands.

export type Role = "partner" | "associate" | "km" | "admin";

export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
  tenant_id: string;
  tenant_name: string;
}

export interface Matter {
  id: string;
  number: string;
  name: string;
  jurisdictions: string[];
  residency: string | null;
  deny_providers: string[];
  allow_providers: string[] | null;
  status: string;
  created_at: string;
}

export type ParseStatus = "uploaded" | "classified" | "unsupported" | "needs_model" | "failed";

export interface DocumentRow {
  id: string;
  matter_id: string;
  filename: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  languages: string[];
  contract_type: string | null;
  contract_type_confidence: number | null;
  governing_law: string | null;
  parties: string[];
  parse_status: ParseStatus;
  error: string | null;
  created_at: string;
}

export interface Clause {
  id: string;
  idx: number;
  number: string | null;
  heading: string;
  text: string;
  taxonomy_key: string;
  confidence: number;
}

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface ReviewStep {
  idx: number;
  name: string;
  status: "pending" | "completed" | "failed";
  attempts: number;
  error: string | null;
  output: Record<string, unknown>;
}

export interface Review {
  id: string;
  matter_id: string;
  document_id: string;
  playbook_key: string;
  playbook_version: number;
  playbook_source: "tenant" | "starter";
  status: RunStatus;
  attempts: number;
  error: string | null;
  cost_usd: number;
  summary: {
    executive_summary?: string;
    negotiation_points?: string[];
    findings?: number;
    needs_human?: number;
  };
  created_at: string;
  finished_at: string | null;
  steps: ReviewStep[];
}

export type CitationStatus =
  | "supported"
  | "partial"
  | "contradicted"
  | "not_found"
  | "uncited"
  | "invalid_source"
  | "not_in_force"
  | "misquoted";

export interface Citation {
  id: string;
  claim_text: string;
  source_unit_id: string | null;
  pinpoint: string | null;
  status: CitationStatus;
  score: number;
  checker: string;
  override_reason: string | null;
}

export type Severity = "high" | "medium" | "low" | "info";
export type Classification = "standard" | "fallback" | "non_standard" | "missing" | "legal_note";
export type Disposition = "accepted" | "edited" | "rejected" | "deferred";

export interface Finding {
  id: string;
  clause_id: string | null;
  clause_key: string;
  rule_key: string;
  kind: "playbook" | "law";
  classification: Classification;
  severity: Severity;
  summary: string;
  rationale: string;
  suggested_redline: string | null;
  confidence: number;
  model_tier: string | null;
  escalated: boolean;
  status: "needs_review" | "needs_human";
  disposition: Disposition | null;
  edited_text: string | null;
  reason_code: string | null;
  note: string | null;
  citations: Citation[];
}

export interface GateBlock {
  type: "finding_undispositioned" | "citation_unsupported" | "review_not_completed";
  finding_id?: string;
  citation_id?: string;
  severity?: Severity;
  summary?: string;
  status?: string;
}

export interface ExportGate {
  open: boolean;
  blocking: GateBlock[];
}

export interface ExportRow {
  id: string;
  run_id: string;
  format: "redline_docx" | "memo_docx";
  filename: string;
  sha256: string;
  created_at: string;
}

export interface LegalUnit {
  id: string;
  source_id: string;
  source_title: string;
  jurisdiction: string;
  unit_path: string;
  pinpoint: string;
  heading: string;
  text: string;
  status: string;
  effective_from: string | null;
  effective_to: string | null;
  official_url: string | null;
  is_fixture: boolean;
  review_status: "unverified" | "verified";
  verified_at: string | null;
  retrieved_at: string | null;
  snapshot_sha256: string | null;
}

export interface RoutingRow {
  id: string;
  task_type: string;
  chosen_endpoint: string | null;
  chosen_tier: string | null;
  outcome: string;
  escalation_reason: string | null;
  filtered: { endpoint_id: string; provider: string; reason: string }[];
  attempts: { endpoint_id: string; ok: boolean; error: string | null; latency_ms: number }[];
  cost_usd: number;
  latency_ms: number;
  created_at: string;
}

export interface PlaybookSummary {
  key: string;
  version: number;
  name: string;
  source: "tenant" | "starter";
  contract_types: string[];
  governing_laws: string[];
  rules: number;
  spec: { rules: PlaybookRule[] } | null;
}

export interface PlaybookRule {
  key: string;
  clause_key: string;
  required?: boolean;
  standard?: string;
  severity?: Severity;
  rationale?: string;
  redline_template?: string | null;
  min_duration_months?: number | null;
  fallback_min_duration_months?: number | null;
  max_duration_months?: number | null;
  min_amount?: number | null;
  max_amount?: number | null;
  must_include_any?: string[];
  must_not_include_any?: string[];
}

export const REASON_CODES = [
  "wrong_clause_type",
  "playbook_misapplied",
  "law_incorrect",
  "law_outdated",
  "too_aggressive",
  "too_lenient",
  "drafting_style",
  "missing_issue",
  "not_relevant_to_client",
  "other",
] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

export type DispositionAction = "accept" | "edit" | "reject" | "defer" | "reset";

// ---- Admin console ----------------------------------------------------------------------

export interface PolicyDoc {
  version: number;
  yaml: string;
  source: "tenant" | "default";
}

export interface PlanCandidate {
  endpoint_id: string;
  provider: string;
  tier: string;
  est_cost_usd: number;
}

export interface RoutingPlan {
  candidates: PlanCandidate[];
  filtered: { endpoint_id: string; provider: string; reason: string }[];
  preferred_tier: string;
  budget_exceeded: boolean;
}

export interface EndpointInfo {
  id: string;
  provider: string;
  via: string | null;
  model: string;
  tier: string;
  billing: string;
  regions: string[];
  enabled: boolean;
}

export interface Credential {
  provider: string;
  last4: string;
  status: "active" | "revoked";
}

export interface SpendRow {
  key: string | null;
  cost_usd: number;
  calls: number;
}

export interface Spend {
  by_matter: SpendRow[];
  by_task: SpendRow[];
  by_tier: SpendRow[];
}

export interface AuditRow {
  id: number;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  matter_id: string | null;
  result: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface IdpConfig {
  id: string;
  issuer: string;
  client_id: string;
  has_client_secret: boolean;
  email_domains: string[];
  enabled: boolean;
  updated_at: string;
}

export interface AuthSessionRow {
  id: string;
  user_id: string;
  user_email: string | null;
  method: string;
  created_at: string;
  expires_at: string;
  user_agent: string | null;
  current: boolean;
}

export const TASK_TYPES = [
  "classify",
  "clause_extraction",
  "playbook_compare",
  "law_check",
  "validate_claim",
  "redline",
  "memo",
] as const;
