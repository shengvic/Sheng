// Server-safe locale helpers (no React). The UI language is chosen by the `travo_locale`
// cookie, else TRAVO_DEFAULT_LOCALE (the Vietnam pilot sets "vi"), else English.
export type Locale = "vi" | "en";
export const LOCALES: Locale[] = ["vi", "en"];
export const LOCALE_COOKIE = "travo_locale";

export function parseLocale(value: string | null | undefined, fallback: Locale = "en"): Locale {
  return value === "vi" || value === "en" ? value : fallback;
}
