"use client";

import { useRef, useState } from "react";

import { t } from "@/i18n/en";

import { Button, cx } from "./ui";

export function UploadDrop({ onFile, busy }: { onFile: (f: File) => void; busy: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={cx(
        "flex items-center justify-between gap-3 rounded-lg border border-dashed px-4 py-3 text-sm",
        over ? "border-accent bg-accent-soft" : "border-border",
      )}
    >
      <span className="text-muted">{busy ? "Uploading and classifying…" : t.matter.dropHint}</span>
      <input
        ref={input}
        type="file"
        accept=".docx,.pdf,.txt"
        className="sr-only"
        data-testid="upload-input"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      <Button onClick={() => input.current?.click()} disabled={busy}>
        {t.matter.upload}
      </Button>
    </div>
  );
}
