"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, Chip, ErrorNote, Field, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

export function SsoTab() {
  const qc = useQueryClient();
  const router = useRouter();
  const idp = useQuery({ queryKey: ["admin", "idp"], queryFn: api.idp });
  const sessions = useQuery({ queryKey: ["admin", "sessions"], queryFn: api.sessions });
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [domains, setDomains] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [origin, setOrigin] = useState("");
  useEffect(() => setOrigin(window.location.origin), []);
  useEffect(() => {
    if (idp.data) {
      setIssuer(idp.data.issuer);
      setClientId(idp.data.client_id);
      setDomains(idp.data.email_domains.join(", "));
      setEnabled(idp.data.enabled);
    }
  }, [idp.data]);
  const save = useMutation({
    mutationFn: () =>
      api.saveIdp({
        issuer: issuer.trim(),
        client_id: clientId.trim(),
        client_secret: secret || undefined,
        email_domains: domains.split(",").map((d) => d.trim()).filter(Boolean),
        enabled,
      }),
    onSuccess: (d) => {
      setSecret("");
      qc.setQueryData(["admin", "idp"], d);
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeSession(id),
    onSuccess: (_d, id) => {
      if (sessions.data?.find((s) => s.id === id)?.current) router.replace("/login");
      else qc.invalidateQueries({ queryKey: ["admin", "sessions"] });
    },
  });

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Single sign-on (OpenID Connect)</h3>
          {idp.data ? <Chip tone={idp.data.enabled ? "ok" : "warn"}>{idp.data.enabled ? "enabled" : "disabled"}</Chip> : <Chip>not set up</Chip>}
        </div>
        <p className="text-sm text-muted">
          Register Travo in Microsoft Entra ID, Google Workspace or Okta with redirect URI{" "}
          <code className="rounded bg-surface-2 px-1">{origin}/auth/callback</code>.
          Users must already exist in Travo; they are matched by email on first sign-in.
        </p>
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Field label="Issuer URL">
            <input className={inputClass} value={issuer} onChange={(e) => setIssuer(e.target.value)} placeholder="https://login.microsoftonline.com/<tenant>/v2.0" required />
          </Field>
          <Field label="Client ID">
            <input className={inputClass} value={clientId} onChange={(e) => setClientId(e.target.value)} required />
          </Field>
          <Field label="Client secret" help={idp.data?.has_client_secret ? "A secret is stored. Leave blank to keep it." : "Optional for public clients (PKCE only)."}>
            <input className={inputClass} type="password" autoComplete="off" value={secret} onChange={(e) => setSecret(e.target.value)} />
          </Field>
          <Field label="Email domains" help="Comma-separated. Each domain can belong to one firm only.">
            <input className={inputClass} value={domains} onChange={(e) => setDomains(e.target.value)} placeholder="lionpartners.com.sg" required />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled
          </label>
          <div className="md:col-span-2">
            <ErrorNote error={save.error} />
            <Button variant="primary" type="submit" disabled={save.isPending} className="mt-2">
              Save sign-in settings
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <h3 className="px-4 pt-3 font-semibold">Active sessions</h3>
        <ErrorNote error={revoke.error} />
        <table className="mt-2 w-full text-sm" data-testid="sessions-table">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">User</th>
              <th className="px-4 py-2 font-medium">Method</th>
              <th className="px-4 py-2 font-medium">Signed in</th>
              <th className="px-4 py-2 font-medium">Expires</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {sessions.data?.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-muted">
                  No single sign-on sessions.
                </td>
              </tr>
            )}
            {sessions.data?.map((s) => (
              <tr key={s.id} className="border-b border-border last:border-0">
                <td className="px-4 py-2">
                  {s.user_email} {s.current && <Chip tone="accent">you</Chip>}
                </td>
                <td className="px-4 py-2 uppercase">{s.method}</td>
                <td className="px-4 py-2 text-muted">{when(s.created_at)}</td>
                <td className="px-4 py-2 text-muted">{when(s.expires_at)}</td>
                <td className="px-4 py-2 text-right">
                  <Button size="sm" variant="danger" onClick={() => revoke.mutate(s.id)}>
                    Revoke
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
