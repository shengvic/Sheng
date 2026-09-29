import { describe, expect, it, vi } from "vitest";

import { ApiError, createClient } from "./api";

function res(status: number, body: unknown, json = true) {
  return new Response(json ? JSON.stringify(body) : String(body), {
    status,
    headers: { "content-type": json ? "application/json" : "text/plain" },
  });
}

describe("api client (BFF, cookie session)", () => {
  it("never sends a bearer token; sends the CSRF header and same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(200, { id: "f1" }));
    await createClient(fetchMock).disposition("f1", { action: "reject", reason_code: "too_aggressive" });
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init.headers);
    expect(url).toBe("/api/v1/findings/f1");
    expect(init.method).toBe("PATCH");
    expect(init.credentials).toBe("same-origin");
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.get("x-travo-csrf")).toBe("1");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ action: "reject", reason_code: "too_aggressive" });
  });

  it("does not set JSON content type for uploads", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(201, { id: "d1" }));
    await createClient(fetchMock).upload("m1", new File(["x"], "a.txt"));
    const init = fetchMock.mock.calls[0]![1];
    expect(init.body).toBeInstanceOf(FormData);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("encodes ids containing '#', '/' and spaces", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(200, {}));
    await createClient(fetchMock).legalUnit("SG/FIXTURE#s 3");
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/v1/legal-units/SG%2FFIXTURE%23s%203");
  });

  it("raises ApiError with FastAPI detail and export-gate blockers", async () => {
    const blocking = [{ type: "finding_undispositioned", finding_id: "f1" }];
    const fetchMock = vi.fn().mockResolvedValue(res(409, { detail: { blocking } }));
    const err = await createClient(fetchMock).createExport("r1", "memo_docx").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.blocking).toEqual(blocking);
    const v = vi.fn().mockResolvedValue(res(422, { detail: [{ msg: "field required" }] }));
    await expect(createClient(v).me()).rejects.toThrow("field required");
    const s = vi.fn().mockResolvedValue(res(404, { detail: "not found" }));
    await expect(createClient(s).me()).rejects.toThrow("not found");
  });

  it("returns undefined for 204 responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    await expect(createClient(fetchMock).revokeSession("s1")).resolves.toBeUndefined();
  });

  it("builds admin audit queries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(200, []));
    await createClient(fetchMock).audit({ action: "auth.login" });
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/v1/admin/audit?action=auth.login&limit=200");
  });
});
