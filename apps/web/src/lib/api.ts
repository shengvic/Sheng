import type {
  AuditRow,
  AuthSessionRow,
  Citation,
  Credential,
  EndpointInfo,
  IdpConfig,
  PolicyDoc,
  RoutingPlan,
  Spend,
  Clause,
  DocumentRow,
  DispositionAction,
  ExportGate,
  ExportRow,
  Finding,
  LegalUnit,
  Matter,
  Me,
  OutputLanguage,
  PlaybookSummary,
  ReasonCode,
  Review,
  RoutingRow,
} from "./types";

import { CSRF_HEADER } from "./csrf";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(ApiError.describe(status, detail));
  }

  static describe(status: number, detail: unknown): string {
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const d = (detail as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d) && d[0] && typeof d[0] === "object" && "msg" in d[0]) {
        return String((d[0] as { msg: unknown }).msg);
      }
    }
    return `Request failed (${status})`;
  }

  /** Export gate 409s carry {detail: {blocking: [...]}} */
  get blocking(): unknown[] | null {
    const d = (this.detail as { detail?: { blocking?: unknown[] } } | null)?.detail;
    return d && Array.isArray(d.blocking) ? d.blocking : null;
  }
}

type Fetch = typeof fetch;

/** The browser never holds a bearer token: `/api/*` is a same-origin BFF that adds it from an
 * httpOnly cookie (ADR-018). Every call carries the CSRF header the BFF requires. */
export function createClient(fetchImpl: Fetch = (...a) => fetch(...a)) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set(CSRF_HEADER, "1");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const res = await fetchImpl(`/api${path}`, { ...init, headers, credentials: "same-origin" });
    if (res.status === 204) return undefined as T;
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const body = isJson ? await res.json() : await res.text();
    if (!res.ok) throw new ApiError(res.status, body);
    return body as T;
  }

  async function download(path: string): Promise<Blob> {
    const res = await fetchImpl(`/api${path}`, {
      headers: { [CSRF_HEADER]: "1" },
      credentials: "same-origin",
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.blob();
  }

  const json = (body: unknown) => JSON.stringify(body);

  return {
    me: () => request<Me>("/v1/me"),
    matters: () => request<Matter[]>("/v1/matters"),
    matter: (id: string) => request<Matter>(`/v1/matters/${id}`),
    createMatter: (body: {
      number: string;
      name: string;
      jurisdictions: string[];
      deny_providers: string[];
      residency?: string | null;
    }) => request<Matter>("/v1/matters", { method: "POST", body: json(body) }),
    documents: (matterId: string) => request<DocumentRow[]>(`/v1/matters/${matterId}/documents`),
    document: (id: string) => request<DocumentRow>(`/v1/documents/${id}`),
    upload: (matterId: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<DocumentRow>(`/v1/matters/${matterId}/documents`, { method: "POST", body: form });
    },
    clauses: (documentId: string) => request<Clause[]>(`/v1/documents/${documentId}/clauses`),
    startReview: (documentId: string, playbookKey?: string, outputLanguage?: OutputLanguage) =>
      request<Review>(`/v1/documents/${documentId}/reviews`, {
        method: "POST",
        body: json({
          ...(playbookKey ? { playbook_key: playbookKey } : {}),
          ...(outputLanguage ? { output_language: outputLanguage } : {}),
        }),
      }),
    reviews: (matterId: string) => request<Review[]>(`/v1/matters/${matterId}/reviews`),
    review: (id: string) => request<Review>(`/v1/reviews/${id}`),
    findings: (id: string) => request<Finding[]>(`/v1/reviews/${id}/findings`),
    routing: (id: string) => request<RoutingRow[]>(`/v1/reviews/${id}/routing`),
    gate: (id: string) => request<ExportGate>(`/v1/reviews/${id}/export-gate`),
    disposition: (
      findingId: string,
      body: { action: DispositionAction; edited_text?: string; reason_code?: ReasonCode; note?: string },
    ) => request<Finding>(`/v1/findings/${findingId}`, { method: "PATCH", body: json(body) }),
    overrideCitation: (citationId: string, reason: string) =>
      request<Citation>(`/v1/citations/${citationId}/override`, { method: "POST", body: json({ reason }) }),
    createExport: (runId: string, format: ExportRow["format"]) =>
      request<ExportRow>(`/v1/reviews/${runId}/exports`, { method: "POST", body: json({ format }) }),
    downloadExport: (exportId: string) => download(`/v1/exports/${exportId}`),
    legalUnit: (unitId: string) => request<LegalUnit>(`/v1/legal-units/${encodeURIComponent(unitId)}`),
    playbooks: () => request<PlaybookSummary[]>("/v1/playbooks"),
    playbook: (key: string) => request<PlaybookSummary>(`/v1/playbooks/${encodeURIComponent(key)}`),

    // Admin console (admin role; the API enforces it).
    policy: () => request<PolicyDoc>("/v1/admin/model-policy"),
    savePolicy: (yaml: string) => request<PolicyDoc>("/v1/admin/model-policy", { method: "PUT", body: json({ yaml }) }),
    dryRun: (body: { task_type: string; matter_id?: string; escalation_reason?: string; yaml?: string }) =>
      request<RoutingPlan>("/v1/admin/model-policy/dry-run", { method: "POST", body: json(body) }),
    endpoints: () => request<EndpointInfo[]>("/v1/admin/endpoints"),
    credentials: () => request<Credential[]>("/v1/admin/provider-credentials"),
    addCredential: (provider: string, api_key: string) =>
      request<Credential>("/v1/admin/provider-credentials", { method: "POST", body: json({ provider, api_key }) }),
    revokeCredential: (provider: string) =>
      request<void>(`/v1/admin/provider-credentials/${encodeURIComponent(provider)}`, { method: "DELETE" }),
    spend: () => request<Spend>("/v1/admin/spend"),
    audit: (params: { action?: string; limit?: number } = {}) => {
      const q = new URLSearchParams();
      if (params.action) q.set("action", params.action);
      q.set("limit", String(params.limit ?? 200));
      return request<AuditRow[]>(`/v1/admin/audit?${q}`);
    },
    idp: () => request<IdpConfig | null>("/v1/admin/idp"),
    saveIdp: (body: { issuer: string; client_id: string; client_secret?: string; email_domains: string[]; enabled: boolean }) =>
      request<IdpConfig>("/v1/admin/idp", { method: "PUT", body: json(body) }),
    sessions: () => request<AuthSessionRow[]>("/v1/admin/sessions"),
    revokeSession: (id: string) => request<void>(`/v1/admin/sessions/${id}/revoke`, { method: "POST" }),
  };
}

export const api = createClient();
export type Api = ReturnType<typeof createClient>;
