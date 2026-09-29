import { NextResponse, type NextRequest } from "next/server";

import { checkCsrf } from "@/lib/csrf";
import { SESSION_COOKIE, apiUrl, devLoginEnabled, secureCookies } from "@/lib/server/config";

// POST /auth/dev {token} — development sign-in only (TRAVO_DEV_LOGIN=true). The token goes
// straight into the httpOnly cookie; page scripts never keep it.
export async function POST(request: NextRequest) {
  if (!devLoginEnabled()) return NextResponse.json({ detail: "not found" }, { status: 404 });
  const bad = checkCsrf("POST", request.headers, request.headers.get("host"));
  if (bad) return NextResponse.json({ detail: bad }, { status: 403 });
  const body = (await request.json().catch(() => ({}))) as { token?: unknown };
  const token = typeof body.token === "string" ? body.token.trim() : "";
  if (!token) return NextResponse.json({ detail: "token required" }, { status: 422 });
  const me = await fetch(`${apiUrl()}/v1/me`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  }).catch(() => null);
  if (!me || !me.ok) return NextResponse.json({ detail: "That token was not accepted." }, { status: 401 });
  const out = new NextResponse(null, { status: 204 });
  out.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookies(),
    path: "/",
    maxAge: 12 * 3600,
  });
  return out;
}
