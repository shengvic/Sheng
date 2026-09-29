"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, Field, inputClass } from "@/components/ui";
import { t } from "@/i18n/en";
import { ApiError, createClient, tokenStore } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createClient(undefined, () => token.trim()).me();
      tokenStore.set(token);
      router.replace("/matters");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t.auth.invalid : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-xl border border-border bg-surface p-6">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="grid h-7 w-7 place-items-center rounded bg-accent text-sm text-accent-ink">T</span>
          {t.auth.title}
        </div>
        <Field label={t.auth.tokenLabel} help={t.auth.tokenHelp}>
          <textarea
            className={`${inputClass} h-24 py-2 font-mono text-xs`}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
            autoFocus
            aria-label={t.auth.tokenLabel}
          />
        </Field>
        {error && <ErrorNote error={error} />}
        <Button variant="primary" type="submit" disabled={busy || !token.trim()} className="w-full">
          {t.auth.submit}
        </Button>
      </form>
    </main>
  );
}
