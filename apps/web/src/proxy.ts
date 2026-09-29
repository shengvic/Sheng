import { NextResponse, type NextRequest } from "next/server";

import { buildCsp, needsSession } from "@/lib/csp";

const SESSION_COOKIE = "travo_session";

// Pages only (see matcher): per-request CSP nonce, and a redirect to /login without a session
// cookie. Validity of the session itself is enforced by the API on every call.
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (needsSession(pathname) && !request.cookies.has(SESSION_COOKIE)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = buildCsp(nonce, process.env.NODE_ENV === "development");
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const res = NextResponse.next({ request: { headers } });
  res.headers.set("Content-Security-Policy", csp);
  return res;
}

export const config = {
  matcher: [
    {
      source: "/((?!api/|auth/|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
