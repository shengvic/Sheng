import "server-only";

export const SESSION_COOKIE = "travo_session";
export const OIDC_COOKIE = "travo_oidc";

export const apiUrl = () => (process.env.TRAVO_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Dev-token sign-in form; never enable where client data lives (ADR-018). */
export const devLoginEnabled = () => process.env.TRAVO_DEV_LOGIN === "true";

/** Secure cookies everywhere except local http development. */
export const secureCookies = () =>
  process.env.NODE_ENV === "production" && process.env.TRAVO_INSECURE_COOKIES !== "true";

/** Public origin used for the OIDC redirect_uri (behind a proxy, set TRAVO_PUBLIC_URL). */
export function publicOrigin(requestUrl: string): string {
  return (process.env.TRAVO_PUBLIC_URL ?? new URL(requestUrl).origin).replace(/\/$/, "");
}

