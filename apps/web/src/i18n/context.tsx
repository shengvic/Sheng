"use client";

import { createContext, useContext, type ReactNode } from "react";

import { humanize } from "@/lib/findings";
import type { Finding } from "@/lib/types";

import { en, type Dict } from "./en";
import { LOCALE_COOKIE, type Locale } from "./locale";
import { vi } from "./vi";

const DICTS: Record<Locale, Dict> = { en, vi };
const I18n = createContext<{ locale: Locale; t: Dict }>({ locale: "en", t: en });

export function I18nProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  return <I18n.Provider value={{ locale, t: DICTS[locale] }}>{children}</I18n.Provider>;
}

export const useT = (): Dict => useContext(I18n).t;
export const useLocale = (): Locale => useContext(I18n).locale;

/** Remember the choice for a year and re-render server components in the new language. */
export function chooseLocale(locale: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; samesite=lax`;
  window.location.reload();
}

export function clauseName(t: Dict, key: string): string {
  return t.clauseNames[key] ?? humanize(key);
}

/** Card title: the discrepancy type for VI/EN findings, else the clause (or rule) name. */
export function findingTitle(t: Dict, f: Finding): string {
  if (f.kind === "bilingual") {
    const type = t.bilingualTypes[f.evidence?.type ?? ""] ?? humanize(f.rule_key);
    return f.clause_id ? `${type} — ${clauseName(t, f.clause_key)}` : type;
  }
  return t.clauseNames[f.clause_key] ? clauseName(t, f.clause_key) : humanize(f.rule_key);
}
