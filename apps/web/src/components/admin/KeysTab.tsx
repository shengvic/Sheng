"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Chip, ErrorNote, Field, inputClass } from "@/components/ui";
import { api } from "@/lib/api";

export function KeysTab() {
  const qc = useQueryClient();
  const creds = useQuery({ queryKey: ["admin", "credentials"], queryFn: api.credentials });
  const endpoints = useQuery({ queryKey: ["admin", "endpoints"], queryFn: api.endpoints });
  const byoProviders = [...new Set((endpoints.data ?? []).filter((e) => e.billing === "byo").map((e) => e.provider))];
  const [provider, setProvider] = useState("");
  const [key, setKey] = useState("");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "credentials"] });
    qc.invalidateQueries({ queryKey: ["admin", "endpoints"] });
  };
  const add = useMutation({
    mutationFn: () => api.addCredential(provider || byoProviders[0] || "", key),
    onSuccess: () => {
      setKey("");
      refresh();
    },
  });
  const revoke = useMutation({ mutationFn: (p: string) => api.revokeCredential(p), onSuccess: refresh });

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <h3 className="font-semibold">Firm API keys (bring your own)</h3>
        <p className="text-sm text-muted">
          Keys are encrypted with your firm&apos;s key and never shown again. Travo uses them only for the providers your
          policy allows, and never for matters that block the provider.
        </p>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate();
          }}
        >
          <Field label="Provider">
            <select className={inputClass} value={provider || byoProviders[0] || ""} onChange={(e) => setProvider(e.target.value)} aria-label="Provider">
              {byoProviders.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Field>
          <Field label="API key">
            <input
              className={`${inputClass} w-80 font-mono`}
              type="password"
              autoComplete="off"
              value={key}
              minLength={8}
              onChange={(e) => setKey(e.target.value)}
              aria-label="API key"
              required
            />
          </Field>
          <Button variant="primary" type="submit" disabled={add.isPending || key.length < 8}>
            Save key
          </Button>
        </form>
        <ErrorNote error={add.error ?? revoke.error} />
      </Card>
      <Card>
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Provider</th>
              <th className="px-4 py-2 font-medium">Key</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {creds.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-3 text-muted">
                  No keys saved.
                </td>
              </tr>
            )}
            {creds.data?.map((c) => (
              <tr key={c.provider} className="border-b border-border last:border-0" data-testid={`key-${c.provider}`}>
                <td className="px-4 py-2 font-medium">{c.provider}</td>
                <td className="px-4 py-2 font-mono text-xs">{c.status === "active" ? `•••• ${c.last4}` : "—"}</td>
                <td className="px-4 py-2">
                  <Chip tone={c.status === "active" ? "ok" : "neutral"}>{c.status}</Chip>
                </td>
                <td className="px-4 py-2 text-right">
                  {c.status === "active" && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => window.confirm(`Revoke the ${c.provider} key?`) && revoke.mutate(c.provider)}
                    >
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
