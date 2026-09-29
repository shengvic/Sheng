// Content Security Policy for pages (docs/06). Scripts need the per-request nonce; styles allow
// inline because React/Next emit style attributes. The IdP is reached by top-level redirects
// only, so no third-party origins are needed.
export function buildCsp(nonce: string, dev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self'${dev ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}

const PUBLIC_PAGES = ["/login"];

export function needsSession(pathname: string): boolean {
  return !PUBLIC_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
