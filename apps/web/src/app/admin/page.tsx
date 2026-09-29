"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AuditTab } from "@/components/admin/AuditTab";
import { KeysTab } from "@/components/admin/KeysTab";
import { PolicyTab } from "@/components/admin/PolicyTab";
import { SpendTab } from "@/components/admin/SpendTab";
import { SsoTab } from "@/components/admin/SsoTab";
import { ErrorNote, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";

const TABS = [
  { id: "policy", label: "Model policy", View: PolicyTab },
  { id: "keys", label: "API keys", View: KeysTab },
  { id: "spend", label: "Spend", View: SpendTab },
  { id: "audit", label: "Audit log", View: AuditTab },
  { id: "sso", label: "Sign-in (SSO)", View: SsoTab },
] as const;

export default function AdminPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("policy");
  if (me.isLoading) return <Spinner />;
  if (me.data?.role !== "admin") return <ErrorNote error="The admin console is for firm administrators." />;
  const Active = TABS.find((t) => t.id === tab)!.View;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Admin</h1>
        <p className="text-sm text-muted">
          {me.data.tenant_name}. Admins manage policy and security; client matters remain visible only to their members.
        </p>
      </div>
      <div role="tablist" aria-label="Admin sections" className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm",
              tab === t.id ? "border-accent font-medium text-text" : "border-transparent text-muted hover:text-text",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        <Active />
      </div>
    </div>
  );
}
