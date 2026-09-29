import type {
  Citation,
  Clause,
  DocumentRow,
  DispositionAction,
  ExportGate,
  ExportRow,
  Finding,
  LegalUnit,
  Matter,
  Me,
  PlaybookSummary,
  ReasonCode,
  Review,
  RoutingRow,
} from "./types";

const TOKEN_KEY = "travo.token";

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

export interface Storage {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
  removeItem(k: string): void;
}

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export const tokenStore = {
  get: (s: Storage | null = storage()) => s?.getItem(TOKEN_KEY) ?? null,
  set: (t: string, s: Storage | null = storage()) => s?.setItem(TOKEN_KEY, t.trim()),
  clear: (s: Storage | null = storage()) => s?.removeItem(TOKEN_KEY),
};

type Fetch = typeof fetch;

export function createClient(fetchImpl: Fetch = (...a) => fetch(...a), getToken = () => tokenStore.get()) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const res = await fetchImpl(`/api${path}`, { ...init, headers });
    if (res.status === 204) return undefined as T;
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const body = isJson ? await res.json() : await res.text();
    if (!res.ok) throw new ApiError(res.status, body);
    return body as T;
  }

  async function download(path: string): Promise<Blob> {
    const token = getToken();
    const res = await fetchImpl(`/api${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
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
    startReview: (documentId: string, playbookKey?: string) =>
      request<Review>(`/v1/documents/${documentId}/reviews`, {
        method: "POST",
        body: json(playbookKey ? { playbook_key: playbookKey } : {}),
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
  };
}

export const api = createClient();
export type Api = ReturnType<typeof createClient>;
