"use client";

import { chooseLocale, useLocale, useT } from "@/i18n/context";
import { LOCALES, type Locale } from "@/i18n/locale";

const SHORT: Record<Locale, string> = { vi: "VI", en: "EN" };

export function LanguageSwitch() {
  const t = useT();
  const locale = useLocale();
  return (
    <div role="group" aria-label={t.common.language} className="flex overflow-hidden rounded-md border border-border text-xs">
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={locale === l}
          onClick={() => l !== locale && chooseLocale(l)}
          className={locale === l ? "bg-surface-2 px-2 py-1 font-semibold" : "px-2 py-1 text-muted hover:text-text"}
        >
          {SHORT[l]}
        </button>
      ))}
    </div>
  );
}
