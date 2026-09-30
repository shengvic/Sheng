/**
 * The browser's address for the API's sign-in rate limit. The platform proxy (Traefik in
 * Coolify) appends the peer it saw to X-Forwarded-For, so the rightmost entry is the one a
 * client cannot forge; entries to its left are client-supplied.
 */
export function clientIp(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for");
  const last = forwarded?.split(",").map((s) => s.trim()).filter(Boolean).pop();
  return last || headers.get("x-real-ip") || "unknown";
}
