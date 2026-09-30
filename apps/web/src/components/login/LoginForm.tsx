"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, Field, inputClass } from "@/components/ui";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { useT } from "@/i18n/context";
import { CSRF_HEADER } from "@/lib/csrf";
import { safeNext } from "@/lib/pkce";

export function LoginForm({ devLogin, error, next }: { devLogin: boolean; error: string | null; next: string | null }) {
  const t = useT();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [devError, setDevError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const target = safeNext(next);

  async function devSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setDevError(null);
    const res = await fetch("/auth/dev", {
      method: "POST",
      headers: { "content-type": "application/json", [CSRF_HEADER]: "1" },
      body: JSON.stringify({ token }),
    }).catch(() => null);
    setBusy(false);
    if (res?.status === 204) router.replace(target);
    else setDevError(t.auth.invalid);
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-border bg-surface p-6">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="grid h-7 w-7 place-items-center rounded bg-accent text-sm text-accent-ink">T</span>
          {t.auth.title}
          <span className="ml-auto font-normal">
            <LanguageSwitch />
          </span>
        </div>
        {error && <ErrorNote error={t.auth.errors[error] ?? t.auth.errors.signin_failed} />}
        {/* Navigate (not submit): CSP form-action would block the redirect on to the IdP. */}
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            const q = new URLSearchParams({ email: email.trim(), next: target });
            window.location.assign(`/auth/login?${q}`);
          }}
        >
          <Field label={t.auth.emailLabel} help={t.auth.ssoHelp}>
            <input
              className={inputClass}
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </Field>
          <Button variant="primary" type="submit" className="w-full">
            {t.auth.sso}
          </Button>
        </form>
        {devLogin && (
          <details className="rounded-md border border-dashed border-border p-3">
            <summary className="cursor-pointer text-sm text-muted">{t.auth.devTitle}</summary>
            <form onSubmit={devSubmit} className="mt-3 space-y-3">
              <Field label={t.auth.tokenLabel} help={t.auth.tokenHelp}>
                <textarea
                  className={`${inputClass} h-20 py-2 font-mono text-xs`}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
              </Field>
              {devError && <ErrorNote error={devError} />}
              <Button type="submit" disabled={busy || !token.trim()} className="w-full">
                {t.auth.submit}
              </Button>
            </form>
          </details>
        )}
      </div>
    </main>
  );
}
