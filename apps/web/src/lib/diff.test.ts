import { describe, expect, it } from "vitest";

import { wordDiff } from "./diff";

describe("wordDiff", () => {
  it("marks replaced words", () => {
    const parts = wordDiff("continues for 2 years from today", "continues for five (5) years from today");
    expect(parts.filter((p) => p.op === "del").map((p) => p.text.trim())).toEqual(["2"]);
    expect(parts.filter((p) => p.op === "ins").map((p) => p.text.trim())).toEqual(["five (5)"]);
    const rebuilt = parts.filter((p) => p.op !== "del").map((p) => p.text).join("");
    expect(rebuilt).toBe("continues for five (5) years from today");
  });

  it("handles insert-only (missing clause) and delete-only", () => {
    expect(wordDiff("", "New clause")).toEqual([{ op: "ins", text: "New clause" }]);
    expect(wordDiff("Old", "")).toEqual([{ op: "del", text: "Old" }]);
  });
});
