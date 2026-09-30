import { NextResponse, type NextRequest } from "next/server";

import { clientIp } from "@/lib/forwarded";
import {
  OIDC_COOKIE,
  SESSION_COOKIE,
  apiUrl,
  publicOrigin,
  secureCookies,
} from "@/lib/server/config";
import { decodeTxn } from "@/lib/server/oidcCookie";

// GET /auth/callback?code=…&state=… — IdP redirects here; the API exchanges the code.
export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.url);
  const params = request.nextUrl.searchParams;
  const txn = decodeTxn(request.cookies.get(OIDC_COOKIE)?.value);
  const fail = (error: string) => {
    const r = NextResponse.redirect(`${origin}/login?error=${error}`, 303);
    r.cookies.delete({ name: OIDC_COOKIE, path: "/auth" });
    return r;
  };
  if (params.get("error")) return fail("denied");
  const code = params.get("code");
  if (!txn || !code || params.get("state") !== txn.state) return fail("signin_failed");

  const res = await fetch(`${apiUrl()}/v1/auth/oidc/callback`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "user-agent": request.headers.get("user-agent") ?? "",
      "x-travo-client-ip": clientIp(request.headers),
    },
    body: JSON.stringify({
      idp_id: txn.idpId,
      code,
      code_verifier: txn.verifier,
      redirect_uri: txn.redirectUri,
      nonce: txn.nonce,
    }),
    cache: "no-store",
  }).catch(() => null);
  if (res?.status === 429) return fail("rate_limited");
  if (!res || !res.ok) return fail("signin_failed");
  const session = (await res.json()) as { token: string; expires_at: string };

  const out = NextResponse.redirect(`${origin}${txn.next}`, 303);
  out.cookies.delete({ name: OIDC_COOKIE, path: "/auth" });
  out.cookies.set(SESSION_COOKIE, session.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookies(),
    path: "/",
    expires: new Date(session.expires_at),
  });
  return out;
}
