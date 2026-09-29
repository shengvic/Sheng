import { describe, expect, it } from "vitest";

import { keyToAction, moveIndex } from "./keyboard";

describe("review shortcuts", () => {
  it("maps keys to actions", () => {
    expect(keyToAction({ key: "j" })).toEqual({ type: "move", delta: 1 });
    expect(keyToAction({ key: "K" })).toEqual({ type: "move", delta: -1 });
    expect(keyToAction({ key: "a" })).toEqual({ type: "accept" });
    expect(keyToAction({ key: "r" })).toEqual({ type: "reject" });
    expect(keyToAction({ key: "?" })).toEqual({ type: "help" });
    expect(keyToAction({ key: "x" })).toBeNull();
  });

  it("never fires while typing or with modifiers, except Escape", () => {
    expect(keyToAction({ key: "a", targetTag: "TEXTAREA" })).toBeNull();
    expect(keyToAction({ key: "a", targetTag: "INPUT" })).toBeNull();
    expect(keyToAction({ key: "a", targetEditable: true })).toBeNull();
    expect(keyToAction({ key: "a", metaKey: true })).toBeNull();
    expect(keyToAction({ key: "Escape", targetTag: "INPUT" })).toEqual({ type: "escape" });
  });

  it("moves within bounds", () => {
    expect(moveIndex(-1, 1, 3)).toBe(0);
    expect(moveIndex(-1, -1, 3)).toBe(2);
    expect(moveIndex(2, 1, 3)).toBe(2);
    expect(moveIndex(0, -1, 3)).toBe(0);
    expect(moveIndex(0, 1, 0)).toBe(-1);
  });
});
