"use client";

import { useRef, useState } from "react";

import { useT } from "@/i18n/context";

import { Button, cx } from "./ui";

export function UploadDrop({ onFile, busy }: { onFile: (f: File) => void; busy: boolean }) {
  const t = useT();
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
      <span className="text-muted">{busy ? t.matter.uploading : t.matter.dropHint}</span>
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
