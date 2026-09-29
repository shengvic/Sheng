// Short-lived login transaction state, kept in an httpOnly cookie between /auth/login and
// /auth/callback. It holds no credentials: state, nonce, PKCE verifier and the IdP id.

export interface OidcTxn {
  state: string;
  nonce: string;
  verifier: string;
  idpId: string;
  redirectUri: string;
  next: string;
}

export function encodeTxn(t: OidcTxn): string {
  return Buffer.from(JSON.stringify(t), "utf8").toString("base64url");
}

export function decodeTxn(raw: string | undefined): OidcTxn | null {
  if (!raw) return null;
  try {
    const t = JSON.parse(Buffer.from(raw, "base64url").toString("utf8")) as Partial<OidcTxn>;
    const keys = ["state", "nonce", "verifier", "idpId", "redirectUri", "next"] as const;
    return keys.every((k) => typeof t[k] === "string" && t[k]) ? (t as OidcTxn) : null;
  } catch {
    return null;
  }
}
