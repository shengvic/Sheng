import { describe, expect, it, vi } from "vitest";

import { ApiError, createClient, tokenStore, type Storage } from "./api";

function res(status: number, body: unknown, json = true) {
  return new Response(json ? JSON.stringify(body) : String(body), {
    status,
    headers: { "content-type": json ? "application/json" : "text/plain" },
  });
}

describe("api client", () => {
  it("sends bearer token and JSON body through the same-origin proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(200, { id: "f1" }));
    const client = createClient(fetchMock, () => "tok-123");
    await client.disposition("f1", { action: "reject", reason_code: "too_aggressive" });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/findings/f1");
    expect(init.method).toBe("PATCH");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-123");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ action: "reject", reason_code: "too_aggressive" });
  });

  it("does not set JSON content type for uploads", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(201, { id: "d1" }));
    await createClient(fetchMock, () => "t").upload("m1", new File(["x"], "a.txt"));
    const init = fetchMock.mock.calls[0]![1];
    expect(init.body).toBeInstanceOf(FormData);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("encodes legal unit ids that contain '#', '/' and spaces", async () => {
    const fetchMock = vi.fn().mockResolvedValue(res(200, {}));
    await createClient(fetchMock, () => "t").legalUnit("SG/FIXTURE#s 3");
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/v1/legal-units/SG%2FFIXTURE%23s%203");
  });

  it("raises ApiError with FastAPI detail and export-gate blockers", async () => {
    const blocking = [{ type: "finding_undispositioned", finding_id: "f1" }];
    const fetchMock = vi.fn().mockResolvedValue(res(409, { detail: { blocking } }));
    const err = await createClient(fetchMock, () => "t").createExport("r1", "memo_docx").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.blocking).toEqual(blocking);

    const v = vi.fn().mockResolvedValue(res(422, { detail: [{ msg: "field required" }] }));
    await expect(createClient(v, () => "t").me()).rejects.toThrow("field required");
    const s = vi.fn().mockResolvedValue(res(404, { detail: "not found" }));
    await expect(createClient(s, () => "t").me()).rejects.toThrow("not found");
  });

  it("returns undefined for 204 responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    await expect(createClient(fetchMock, () => "t").me()).resolves.toBeUndefined();
  });

  it("token store trims and clears", () => {
    const m = new Map<string, string>();
    const s: Storage = {
      getItem: (k) => m.get(k) ?? null,
      setItem: (k, v) => void m.set(k, v),
      removeItem: (k) => void m.delete(k),
    };
    tokenStore.set("  abc \n", s);
    expect(tokenStore.get(s)).toBe("abc");
    tokenStore.clear(s);
    expect(tokenStore.get(s)).toBeNull();
    expect(tokenStore.get(null)).toBeNull();
  });
});
