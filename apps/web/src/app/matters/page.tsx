"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, Chip, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { t } from "@/i18n/en";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

const JURISDICTIONS = ["SG", "MY", "VN", "ID"] as const;

function NewMatter({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [juris, setJuris] = useState<string[]>(["SG"]);
  const [deny, setDeny] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api.createMatter({
        number,
        name,
        jurisdictions: juris,
        deny_providers: deny
          .split(",")
          .map((s) => s.trim().toLowerCase())
          .filter(Boolean),
      }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["matters"] });
      onDone();
      router.push(`/matters/${m.id}`);
    },
  });
  return (
    <Card className="p-4">
      <form
        className="grid gap-3 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label={t.matters.number}>
          <input className={inputClass} value={number} onChange={(e) => setNumber(e.target.value)} required />
        </Field>
        <Field label={t.matters.name}>
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <fieldset className="flex flex-col gap-1 text-sm">
          <legend className="mb-1 font-medium">{t.matters.jurisdictions}</legend>
          <div className="flex gap-3">
            {JURISDICTIONS.map((j) => (
              <label key={j} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={juris.includes(j)}
                  onChange={(e) => setJuris(e.target.checked ? [...juris, j] : juris.filter((x) => x !== j))}
                />
                {j}
              </label>
            ))}
          </div>
        </fieldset>
        <Field label={t.matters.deny} help={t.matters.denyHelp}>
          <input className={inputClass} value={deny} onChange={(e) => setDeny(e.target.value)} placeholder="openai" />
        </Field>
        <div className="flex items-center gap-2 md:col-span-2">
          <Button variant="primary" type="submit" disabled={create.isPending}>
            {t.matters.save}
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
          <ErrorNote error={create.error} />
        </div>
      </form>
    </Card>
  );
}

export default function MattersPage() {
  const matters = useQuery({ queryKey: ["matters"], queryFn: api.matters });
  const [creating, setCreating] = useState(false);
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t.matters.title}</h1>
        {!creating && (
          <Button variant="primary" onClick={() => setCreating(true)}>
            {t.matters.create}
          </Button>
        )}
      </div>
      {creating && <NewMatter onDone={() => setCreating(false)} />}
      {matters.isLoading && <Spinner />}
      <ErrorNote error={matters.error} />
      {matters.data && matters.data.length === 0 && <p className="text-muted">{t.matters.empty}</p>}
      {matters.data && matters.data.length > 0 && (
        <Card>
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Number</th>
                <th className="px-4 py-2 font-medium">Matter</th>
                <th className="px-4 py-2 font-medium">Jurisdictions</th>
                <th className="px-4 py-2 font-medium">Model policy</th>
                <th className="px-4 py-2 font-medium">Opened</th>
              </tr>
            </thead>
            <tbody>
              {matters.data.map((m) => (
                <tr key={m.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                  <td className="px-4 py-2 font-mono text-xs">{m.number}</td>
                  <td className="px-4 py-2">
                    <Link href={`/matters/${m.id}`} className="font-medium text-accent hover:underline">
                      {m.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{m.jurisdictions.join(", ")}</td>
                  <td className="px-4 py-2">
                    {m.deny_providers.length ? (
                      <Chip tone="warn">No {m.deny_providers.join(", ")}</Chip>
                    ) : (
                      <span className="text-muted">Firm default</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-muted">{when(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
