"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { StepProgress } from "@/components/StepProgress";
import { UploadDrop } from "@/components/UploadDrop";
import { Button, Card, Chip, ErrorNote, Spinner, cx, inputClass } from "@/components/ui";
import { t } from "@/i18n/en";
import { api } from "@/lib/api";
import { bytes, usd, when } from "@/lib/format";
import type { DocumentRow, Review } from "@/lib/types";

const STATUS_TONE: Record<string, "ok" | "warn" | "bad" | "neutral"> = {
  classified: "ok",
  completed: "ok",
  running: "warn",
  queued: "neutral",
  uploaded: "neutral",
  needs_model: "bad",
  unsupported: "bad",
  failed: "bad",
};

function DocumentRowView({ doc, reviews }: { doc: DocumentRow; reviews: Review[] }) {
  const qc = useQueryClient();
  const router = useRouter();
  const playbooks = useQuery({ queryKey: ["playbooks"], queryFn: api.playbooks });
  const [playbook, setPlaybook] = useState("");
  const start = useMutation({
    mutationFn: () => api.startReview(doc.id, playbook || undefined),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["reviews", doc.matter_id] });
      router.push(`/reviews/${r.id}`);
    },
  });
  const latest = reviews.find((r) => r.document_id === doc.id);
  return (
    <li className="flex flex-col gap-2 border-b border-border px-4 py-3 last:border-0 md:flex-row md:items-center">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate font-medium">{doc.filename}</span>
          <Chip tone={STATUS_TONE[doc.parse_status] ?? "neutral"}>{doc.parse_status.replace("_", " ")}</Chip>
          {doc.contract_type && <Chip>{doc.contract_type}</Chip>}
          {doc.governing_law && <Chip>{doc.governing_law} law</Chip>}
          {doc.languages.map((l) => (
            <Chip key={l}>{l}</Chip>
          ))}
        </div>
        <div className="mt-0.5 text-xs text-muted">
          {doc.parties.join(" · ") || "Parties not detected"} · {bytes(doc.size_bytes)} · {when(doc.created_at)}
        </div>
        {doc.error && <div className="mt-1 text-xs text-high">{doc.error}</div>}
      </div>
      <div className="flex items-center gap-2">
        {latest && (
          <Link href={`/reviews/${latest.id}`} className="text-sm text-accent hover:underline">
            Open latest review
          </Link>
        )}
        <select
          className={cx(inputClass, "w-48")}
          value={playbook}
          onChange={(e) => setPlaybook(e.target.value)}
          aria-label="Playbook"
          disabled={doc.parse_status !== "classified"}
        >
          <option value="">{t.matter.playbookAuto}</option>
          {playbooks.data?.map((p) => (
            <option key={`${p.source}:${p.key}`} value={p.key}>
              {p.name} {p.source === "tenant" ? `(firm v${p.version})` : "(starter)"}
            </option>
          ))}
        </select>
        <Button
          variant="primary"
          onClick={() => start.mutate()}
          disabled={doc.parse_status !== "classified" || start.isPending}
        >
          {t.matter.startReview}
        </Button>
      </div>
      {start.error && (
        <div className="md:basis-full">
          <ErrorNote error={start.error} />
        </div>
      )}
    </li>
  );
}

export default function MatterPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const matter = useQuery({ queryKey: ["matter", id], queryFn: () => api.matter(id) });
  const docs = useQuery({ queryKey: ["documents", id], queryFn: () => api.documents(id) });
  const reviews = useQuery({
    queryKey: ["reviews", id],
    queryFn: () => api.reviews(id),
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.status === "queued" || r.status === "running") ? 2000 : false,
  });
  const upload = useMutation({
    mutationFn: (f: File) => api.upload(id, f),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", id] }),
  });

  if (matter.isLoading) return <Spinner />;
  if (matter.error) return <ErrorNote error={matter.error} />;
  const m = matter.data!;
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div>
        <Link href="/matters" className="text-sm text-muted hover:text-text">
          ← {t.nav.matters}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{m.name}</h1>
          <span className="font-mono text-xs text-muted">{m.number}</span>
          <Chip tone="accent" title="Only matter members can see this matter's content">
            🔒 {t.matter.wall}
          </Chip>
          <Chip>{m.jurisdictions.join(" · ") || "No jurisdiction"}</Chip>
          {m.deny_providers.length > 0 && (
            <Chip tone="warn" title="The model router never sends this matter's data to these providers">
              No {m.deny_providers.join(", ")}
            </Chip>
          )}
          {m.residency && <Chip tone="warn">{m.residency} residency</Chip>}
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t.matter.documents}</h2>
        <UploadDrop onFile={(f) => upload.mutate(f)} busy={upload.isPending} />
        <ErrorNote error={upload.error} />
        <Card>
          {docs.isLoading && <div className="p-4"><Spinner /></div>}
          {docs.data?.length === 0 && <p className="p-4 text-muted">{t.matter.noDocs}</p>}
          <ul>
            {docs.data?.map((d) => (
              <DocumentRowView key={d.id} doc={d} reviews={reviews.data ?? []} />
            ))}
          </ul>
        </Card>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t.matter.reviews}</h2>
        <Card>
          {reviews.data?.length === 0 && <p className="p-4 text-muted">{t.matter.noReviews}</p>}
          <ul>
            {reviews.data?.map((r) => {
              const doc = docs.data?.find((d) => d.id === r.document_id);
              return (
                <li key={r.id} className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3 last:border-0">
                  <Link href={`/reviews/${r.id}`} className="font-medium text-accent hover:underline">
                    {doc?.filename ?? "Document"}
                  </Link>
                  <Chip tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Chip>
                  <span className="text-xs text-muted">
                    {r.playbook_key} v{r.playbook_version} · {usd(r.cost_usd)} · {when(r.created_at)}
                  </span>
                  <div className="ml-auto">
                    <StepProgress review={r} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      </section>
    </div>
  );
}
