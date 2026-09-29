import { NextResponse, type NextRequest } from "next/server";

import { authorizeUrl, randomToken, s256, safeNext } from "@/lib/pkce";
import { OIDC_COOKIE, apiUrl, publicOrigin, secureCookies } from "@/lib/server/config";
import { encodeTxn } from "@/lib/server/oidcCookie";

// GET /auth/login?email=…&next=… → redirect to the firm's identity provider.
export async function GET(request: NextRequest) {
  const email = request.nextUrl.searchParams.get("email")?.trim() ?? "";
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const origin = publicOrigin(request.url);
  const fail = (error: string) => NextResponse.redirect(`${origin}/login?error=${error}`, 303);
  if (!/^[^@\s]+@[^@\s]+$/.test(email)) return fail("email");

  const res = await fetch(`${apiUrl()}/v1/auth/oidc/start`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
    cache: "no-store",
  }).catch(() => null);
  if (!res) return fail("unavailable");
  if (res.status === 404) return fail("no_sso");
  if (!res.ok) return fail("unavailable");
  const start = (await res.json()) as {
    idp_id: string;
    authorization_endpoint: string;
    client_id: string;
    scopes: string;
  };

  const state = randomToken();
  const nonce = randomToken();
  const verifier = randomToken(48);
  const redirectUri = `${origin}/auth/callback`;
  const target = authorizeUrl(start.authorization_endpoint, {
    clientId: start.client_id,
    redirectUri,
    state,
    nonce,
    challenge: await s256(verifier),
    scopes: start.scopes,
    loginHint: email,
  });
  const out = NextResponse.redirect(target, 303);
  out.cookies.set(OIDC_COOKIE, encodeTxn({ state, nonce, verifier, idpId: start.idp_id, redirectUri, next }), {
    httpOnly: true,
    sameSite: "lax", // must survive the top-level redirect back from the IdP
    secure: secureCookies(),
    path: "/auth",
    maxAge: 600,
  });
  return out;
}
