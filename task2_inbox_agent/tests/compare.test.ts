import { describe, it, expect } from "vitest";
import { normalize, draftsEqual } from "../src/autonomy/compare.js";

describe("comparison policy", () => {
  it("identical text is equal", () => {
    expect(draftsEqual("hello", "hello")).toBe(true);
  });
  it("whitespace normalization makes them equal", () => {
    expect(draftsEqual("hello   world", "hello world")).toBe(true);
  });
  it("case normalization makes them equal", () => {
    expect(draftsEqual("HELLO", "hello")).toBe(true);
  });
  it("signature block stripped", () => {
    expect(draftsEqual("body\n-- \nSupport Team", "body")).toBe(true);
  });
  it("different text is not equal", () => {
    expect(draftsEqual("hello", "world")).toBe(false);
  });
  it("edit of a word is not equal", () => {
    expect(draftsEqual("reset via settings", "reset via menu")).toBe(false);
  });
  it("normalize is deterministic", () => {
    expect(normalize("A  b\n-- \nS")).toBe(normalize("a b"));
  });
});
