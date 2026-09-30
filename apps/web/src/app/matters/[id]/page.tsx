"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { StepProgress } from "@/components/StepProgress";
import { UploadDrop } from "@/components/UploadDrop";
import { Button, Card, Chip, ErrorNote, Spinner, cx, inputClass } from "@/components/ui";
import { useT } from "@/i18n/context";
import { api } from "@/lib/api";
import { bytes, usd, when } from "@/lib/format";
import type { DocumentRow, OutputLanguage, Review } from "@/lib/types";

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
  const t = useT();
  const qc = useQueryClient();
  const router = useRouter();
  const playbooks = useQuery({ queryKey: ["playbooks"], queryFn: api.playbooks });
  const [playbook, setPlaybook] = useState("");
  const [output, setOutput] = useState<OutputLanguage | "">("");
  const start = useMutation({
    mutationFn: () => api.startReview(doc.id, playbook || undefined, output || undefined),
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
          <Chip tone={STATUS_TONE[doc.parse_status] ?? "neutral"}>
            {t.matter.status[doc.parse_status] ?? doc.parse_status}
          </Chip>
          {doc.contract_type && <Chip>{doc.contract_type}</Chip>}
          {doc.governing_law && <Chip>{t.matter.law(doc.governing_law)}</Chip>}
          {doc.bilingual_layout !== "single" && (
            <Chip tone="accent" data-testid="bilingual-layout">
              {t.matter.layout[doc.bilingual_layout] ?? doc.bilingual_layout}
            </Chip>
          )}
          {doc.languages.map((l) => (
            <Chip key={l}>{l}</Chip>
          ))}
        </div>
        <div className="mt-0.5 text-xs text-muted">
          {doc.parties.join(" · ") || t.matter.partiesUnknown} · {bytes(doc.size_bytes)} · {when(doc.created_at)}
        </div>
        {doc.error && <div className="mt-1 text-xs text-high">{doc.error}</div>}
      </div>
      <div className="flex items-center gap-2">
        {latest && (
          <Link href={`/reviews/${latest.id}`} className="text-sm text-accent hover:underline">
            {t.matter.openLatest}
          </Link>
        )}
        <select
          className={cx(inputClass, "w-48")}
          value={playbook}
          onChange={(e) => setPlaybook(e.target.value)}
          aria-label={t.matter.playbook}
          disabled={doc.parse_status !== "classified"}
        >
          <option value="">{t.matter.playbookAuto}</option>
          {playbooks.data?.map((p) => (
            <option key={`${p.source}:${p.key}`} value={p.key}>
              {p.name} {p.source === "tenant" ? t.matter.firmVersion(p.version) : t.matter.starter}
            </option>
          ))}
        </select>
        <select
          className={cx(inputClass, "w-44")}
          value={output}
          onChange={(e) => setOutput(e.target.value as OutputLanguage | "")}
          aria-label={t.matter.outputLanguage}
          title={t.matter.outputLanguage}
          disabled={doc.parse_status !== "classified"}
        >
          {(["", "vi", "en", "both"] as const).map((o) => (
            <option key={o} value={o}>
              {t.matter.output[o || "auto"]}
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
  const t = useT();
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
          <Chip tone="accent" title={t.matter.wallHelp}>
            🔒 {t.matter.wall}
          </Chip>
          <Chip>{m.jurisdictions.join(" · ") || t.matter.noJurisdiction}</Chip>
          {m.deny_providers.length > 0 && (
            <Chip tone="warn" title={t.matter.denyHelp}>
              {t.matters.noProviders(m.deny_providers.join(", "))}
            </Chip>
          )}
          {m.residency && <Chip tone="warn">{t.matter.residency(m.residency)}</Chip>}
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
                    {doc?.filename ?? t.matter.document}
                  </Link>
                  <Chip tone={STATUS_TONE[r.status] ?? "neutral"}>{t.matter.status[r.status] ?? r.status}</Chip>
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
