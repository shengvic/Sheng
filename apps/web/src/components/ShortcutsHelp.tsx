"use client";

import { useT } from "@/i18n/context";

import { Button } from "./ui";


export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  const t = useT();
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t.review.shortcuts}
        className="w-full max-w-sm rounded-xl border border-border bg-surface p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 font-semibold">{t.review.shortcuts}</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {t.review.shortcutRows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt>
                <kbd className="rounded border border-border bg-surface-2 px-1.5 font-mono text-xs">{k}</kbd>
              </dt>
              <dd className="text-muted">{v}</dd>
            </div>
          ))}
        </dl>
        <Button className="mt-4 w-full" onClick={onClose} autoFocus>
          {t.common.close}
        </Button>
      </div>
    </div>
  );
}
