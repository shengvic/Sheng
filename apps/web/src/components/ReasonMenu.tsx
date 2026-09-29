"use client";

import { useEffect, useRef, useState } from "react";

import { REASON_LABEL, t } from "@/i18n/en";
import { REASON_CODES, type ReasonCode } from "@/lib/types";

import { Button, inputClass } from "./ui";

export function ReasonMenu({
  onSubmit,
  onCancel,
}: {
  onSubmit: (reason: ReasonCode, note: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState<ReasonCode | "">("");
  const [note, setNote] = useState("");
  const first = useRef<HTMLSelectElement>(null);
  useEffect(() => first.current?.focus(), []);
  return (
    <form
      className="space-y-2 rounded-md border border-border bg-surface-2 p-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (reason) onSubmit(reason, note);
      }}
    >
      <select
        ref={first}
        className={`${inputClass} w-full`}
        value={reason}
        onChange={(e) => setReason(e.target.value as ReasonCode)}
        aria-label="Reason for rejecting"
        required
      >
        <option value="">Why reject? (required)</option>
        {REASON_CODES.map((c) => (
          <option key={c} value={c}>
            {REASON_LABEL[c]}
          </option>
        ))}
      </select>
      <input
        className={`${inputClass} w-full`}
        placeholder="Optional note for the team"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        aria-label="Note"
      />
      <div className="flex gap-2">
        <Button type="submit" variant="danger" size="sm" disabled={!reason}>
          {t.review.reject}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          {t.review.cancel}
        </Button>
      </div>
    </form>
  );
}
