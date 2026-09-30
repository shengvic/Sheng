"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AuditTab } from "@/components/admin/AuditTab";
import { KeysTab } from "@/components/admin/KeysTab";
import { PolicyTab } from "@/components/admin/PolicyTab";
import { SpendTab } from "@/components/admin/SpendTab";
import { SsoTab } from "@/components/admin/SsoTab";
import { ErrorNote, Spinner, cx } from "@/components/ui";
import { useT } from "@/i18n/context";
import { api } from "@/lib/api";

// Tab contents stay in English for now (firm IT administrators); labels are localised.
const TABS = [
  { id: "policy", View: PolicyTab },
  { id: "keys", View: KeysTab },
  { id: "spend", View: SpendTab },
  { id: "audit", View: AuditTab },
  { id: "sso", View: SsoTab },
] as const;

export default function AdminPage() {
  const t = useT();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("policy");
  if (me.isLoading) return <Spinner />;
  if (me.data?.role !== "admin") return <ErrorNote error={t.admin.onlyAdmins} />;
  const Active = TABS.find((x) => x.id === tab)!.View;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">{t.admin.title}</h1>
        <p className="text-sm text-muted">{t.admin.intro(me.data.tenant_name)}</p>
      </div>
      <div role="tablist" aria-label={t.admin.sections} className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((x) => (
          <button
            key={x.id}
            role="tab"
            type="button"
            aria-selected={tab === x.id}
            onClick={() => setTab(x.id)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm",
              tab === x.id ? "border-accent font-medium text-text" : "border-transparent text-muted hover:text-text",
            )}
          >
            {t.admin.tabs[x.id]}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        <Active />
      </div>
    </div>
  );
}
