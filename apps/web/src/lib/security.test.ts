import { describe, expect, it } from "vitest";

import { buildCsp, needsSession } from "./csp";
import { checkCsrf } from "./csrf";
import { clientIp } from "./forwarded";
import { authorizeUrl, base64url, randomToken, s256, safeNext } from "./pkce";
import { decodeTxn, encodeTxn } from "./server/oidcCookie";

describe("PKCE", () => {
  it("matches the RFC 7636 appendix B example", async () => {
    expect(await s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).toBe(
      "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    );
  });
  it("random tokens are url-safe and unique", () => {
    const a = randomToken(48);
    expect(a).toMatch(/^[A-Za-z0-9_-]{64}$/);
    expect(randomToken(48)).not.toBe(a);
    expect(base64url(new Uint8Array([251, 255]))).toBe("-_8");
  });
  it("builds the authorize URL", () => {
    const u = new URL(
      authorizeUrl("https://idp.test/authorize?tenant=x", {
        clientId: "c", redirectUri: "https://app.test/auth/callback", state: "s", nonce: "n",
        challenge: "ch", scopes: "openid email", loginHint: "a@b.test",
      }),
    );
    expect(u.searchParams.get("tenant")).toBe("x");
    expect(u.searchParams.get("code_challenge_method")).toBe("S256");
    expect(u.searchParams.get("login_hint")).toBe("a@b.test");
    expect(u.searchParams.get("response_type")).toBe("code");
  });
});

describe("post-login redirect", () => {
  it("only allows same-site app paths", () => {
    expect(safeNext("/reviews/1?x=1")).toBe("/reviews/1?x=1");
    for (const bad of ["https://evil.test", "//evil.test", "/\\evil.test", "/auth/logout", "/api/v1/me", "/login", null, ""]) {
      expect(safeNext(bad)).toBe("/matters");
    }
  });
});

describe("CSRF", () => {
  const h = (o: Record<string, string>) => new Headers(o);
  it("lets safe methods through", () => {
    expect(checkCsrf("GET", h({}), "app.test")).toBeNull();
  });
  it("requires the header and a same-origin Origin for writes", () => {
    expect(checkCsrf("POST", h({ origin: "https://app.test" }), "app.test")).toMatch(/header/);
    expect(checkCsrf("POST", h({ "x-travo-csrf": "1" }), "app.test")).toMatch(/Origin/);
    expect(checkCsrf("PATCH", h({ "x-travo-csrf": "1", origin: "https://evil.test" }), "app.test")).toMatch(/cross-origin/);
    expect(checkCsrf("DELETE", h({ "x-travo-csrf": "1", origin: "https://app.test" }), "app.test")).toBeNull();
  });
});

describe("CSP", () => {
  it("is nonce-based with no unsafe-eval in production", () => {
    const csp = buildCsp("abc", false);
    expect(csp).toContain("script-src 'self' 'nonce-abc' 'strict-dynamic'");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(buildCsp("abc", true)).toContain("'unsafe-eval'");
  });
  it("protects every page except login", () => {
    expect(needsSession("/login")).toBe(false);
    expect(needsSession("/matters")).toBe(true);
    expect(needsSession("/admin")).toBe(true);
    expect(needsSession("/loginx")).toBe(true);
  });
});

describe("login transaction cookie", () => {
  it("round-trips and rejects tampering", () => {
    const t = { state: "s", nonce: "n", verifier: "v", idpId: "i", redirectUri: "r", next: "/matters" };
    expect(decodeTxn(encodeTxn(t))).toEqual(t);
    expect(decodeTxn("not-base64-json")).toBeNull();
    expect(decodeTxn(Buffer.from(JSON.stringify({ state: "s" })).toString("base64url"))).toBeNull();
    expect(decodeTxn(undefined)).toBeNull();
  });
});

describe("client address for the sign-in rate limit", () => {
  it("takes the entry the platform proxy appended, not client-supplied ones", () => {
    const h = new Headers({ "x-forwarded-for": "1.2.3.4, 203.0.113.9" });
    expect(clientIp(h)).toBe("203.0.113.9");
    expect(clientIp(new Headers({ "x-real-ip": "198.51.100.1" }))).toBe("198.51.100.1");
    expect(clientIp(new Headers())).toBe("unknown");
  });
});
