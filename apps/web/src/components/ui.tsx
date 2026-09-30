"use client";

import type { ComponentProps, ReactNode } from "react";

import { useT } from "@/i18n/context";
import type { Severity } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: "sm" | "md" }) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        variant === "primary" && "bg-accent text-accent-ink hover:opacity-90",
        variant === "secondary" && "border border-border bg-surface text-text hover:bg-surface-2",
        variant === "ghost" && "text-muted hover:bg-surface-2 hover:text-text",
        variant === "danger" && "border border-high/40 bg-high-soft text-high hover:border-high",
        className,
      )}
      {...props}
    />
  );
}

const SEVERITY_STYLE: Record<Severity, string> = {
  high: "bg-high-soft text-high",
  medium: "bg-medium-soft text-medium",
  low: "bg-low-soft text-low",
  info: "bg-surface-2 text-muted",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const t = useT();
  return (
    <span
      className={cx(
        "inline-flex h-5 items-center rounded px-1.5 text-[11px] font-semibold uppercase tracking-wide",
        SEVERITY_STYLE[severity],
      )}
    >
      {t.severity[severity] ?? severity}
    </span>
  );
}

export function Chip({
  children,
  tone = "neutral",
  title,
  "data-testid": testId,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "ok" | "warn" | "bad";
  title?: string;
  "data-testid"?: string;
}) {
  return (
    <span
      title={title}
      data-testid={testId}
      className={cx(
        "inline-flex h-5 items-center gap-1 rounded-full border px-2 text-[11px] font-medium",
        tone === "neutral" && "border-border text-muted",
        tone === "accent" && "border-accent/40 bg-accent-soft text-accent",
        tone === "ok" && "border-ok/40 bg-ok-soft text-ok",
        tone === "warn" && "border-medium/40 bg-medium-soft text-medium",
        tone === "bad" && "border-high/40 bg-high-soft text-high",
      )}
    >
      {children}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-lg border border-border bg-surface", className)}>{children}</div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border border-t-accent" />
      <span className="text-sm">{label}…</span>
    </span>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="rounded-md border border-high/40 bg-high-soft px-3 py-2 text-sm text-high">
      {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

export function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {help && <span className="text-xs text-muted">{help}</span>}
    </label>
  );
}

export const inputClass =
  "h-9 rounded-md border border-border bg-surface px-2.5 text-sm text-text placeholder:text-muted";
