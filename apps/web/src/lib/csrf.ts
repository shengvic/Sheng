// CSRF defence for cookie-authenticated requests (ADR-018): state-changing requests must carry
// the custom header (forces a CORS preflight cross-site) and a same-origin Origin header.

export const CSRF_HEADER = "x-travo-csrf";
const SAFE = new Set(["GET", "HEAD", "OPTIONS"]);

export function checkCsrf(method: string, headers: Headers, host: string | null): string | null {
  if (SAFE.has(method.toUpperCase())) return null;
  if (headers.get(CSRF_HEADER) !== "1") return "missing CSRF header";
  const origin = headers.get("origin");
  if (!origin) return "missing Origin";
  try {
    if (!host || new URL(origin).host !== host) return "cross-origin request";
  } catch {
    return "bad Origin";
  }
  return null;
}
