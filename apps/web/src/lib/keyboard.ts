export type KeyAction =
  | { type: "move"; delta: 1 | -1 }
  | { type: "accept" }
  | { type: "edit" }
  | { type: "reject" }
  | { type: "defer" }
  | { type: "sources" }
  | { type: "help" }
  | { type: "escape" };

export interface KeyInput {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  /** Tag name of the focused element, e.g. "INPUT" */
  targetTag?: string;
  targetEditable?: boolean;
}

const MAP: Record<string, KeyAction> = {
  j: { type: "move", delta: 1 },
  ArrowDown: { type: "move", delta: 1 },
  k: { type: "move", delta: -1 },
  ArrowUp: { type: "move", delta: -1 },
  a: { type: "accept" },
  e: { type: "edit" },
  r: { type: "reject" },
  d: { type: "defer" },
  s: { type: "sources" },
  "?": { type: "help" },
  Escape: { type: "escape" },
};

/** Review-canvas shortcuts (docs/08 §3.2). Never fire while typing or with modifiers. */
export function keyToAction(e: KeyInput): KeyAction | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  const typing =
    e.targetEditable || e.targetTag === "INPUT" || e.targetTag === "TEXTAREA" || e.targetTag === "SELECT";
  if (typing) return e.key === "Escape" ? MAP.Escape! : null;
  return MAP[e.key] ?? MAP[e.key.toLowerCase()] ?? null;
}

export function moveIndex(current: number, delta: number, length: number): number {
  if (length === 0) return -1;
  if (current < 0) return delta > 0 ? 0 : length - 1;
  return Math.min(length - 1, Math.max(0, current + delta));
}
