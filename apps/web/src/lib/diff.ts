export type DiffPart = { op: "eq" | "ins" | "del"; text: string };

/** Word-level diff (LCS). Clauses are short enough for O(n·m). */
export function wordDiff(before: string, after: string): DiffPart[] {
  const a = before.split(/(\s+)/).filter((s) => s.length);
  const b = after.split(/(\s+)/).filter((s) => s.length);
  const n = a.length;
  const m = b.length;
  if (n * m > 400_000) {
    return [
      ...(before ? [{ op: "del" as const, text: before }] : []),
      ...(after ? [{ op: "ins" as const, text: after }] : []),
    ];
  }
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i]![j] = a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }
  const out: DiffPart[] = [];
  const push = (op: DiffPart["op"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += text;
    else out.push({ op, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push("eq", a[i]!);
      i++;
      j++;
    } else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) {
      push("del", a[i++]!);
    } else {
      push("ins", b[j++]!);
    }
  }
  while (i < n) push("del", a[i++]!);
  while (j < m) push("ins", b[j++]!);
  return coalesce(out);
}

/** Merge change runs separated only by whitespace into one deletion + one insertion, so
 * "2" → "five (5)" reads as a single replacement (as in Word) instead of fragments. */
function coalesce(parts: DiffPart[]): DiffPart[] {
  const out: DiffPart[] = [];
  let i = 0;
  while (i < parts.length) {
    const p = parts[i]!;
    if (p.op === "eq") {
      out.push(p);
      i++;
      continue;
    }
    let del = "";
    let ins = "";
    while (i < parts.length) {
      const q = parts[i]!;
      if (q.op === "del") del += q.text;
      else if (q.op === "ins") ins += q.text;
      else if (/^\s+$/.test(q.text) && parts[i + 1] && parts[i + 1]!.op !== "eq") {
        del += q.text;
        ins += q.text;
      } else break;
      i++;
    }
    if (del) out.push({ op: "del", text: del });
    if (ins) out.push({ op: "ins", text: ins });
  }
  return out;
}
