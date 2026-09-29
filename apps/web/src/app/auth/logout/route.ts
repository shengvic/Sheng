import { NextResponse, type NextRequest } from "next/server";

import { checkCsrf } from "@/lib/csrf";
import { SESSION_COOKIE, apiUrl } from "@/lib/server/config";

// POST /auth/logout — revoke the server-side session and clear the cookie.
export async function POST(request: NextRequest) {
  const bad = checkCsrf("POST", request.headers, request.headers.get("host"));
  if (bad) return NextResponse.json({ detail: bad }, { status: 403 });
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    await fetch(`${apiUrl()}/v1/auth/logout`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    }).catch(() => null);
  }
  const out = new NextResponse(null, { status: 204 });
  out.cookies.delete(SESSION_COOKIE);
  return out;
}
