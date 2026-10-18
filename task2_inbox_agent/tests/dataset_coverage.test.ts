import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("synthetic email dataset", () => {
  const rows = readFileSync(resolve(process.cwd(), "data/emails_v1.jsonl"), "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l));

  it("has at least 50 records", () => {
    expect(rows.length).toBeGreaterThanOrEqual(50);
  });

  it("covers all 7 categories", () => {
    const cats = new Set(rows.map((r) => r.expected.category));
    for (const c of ["how_to", "troubleshooting", "project_request", "refund_cancellation", "complaint", "quote_request", "follow_up"]) {
      expect(cats.has(c)).toBe(true);
    }
  });

  it("all records are labeled synthetic", () => {
    expect(rows.every((r) => r.is_synthetic === true)).toBe(true);
  });

  it("every record has expected behavior and risk", () => {
    for (const r of rows) {
      expect(r.expected.behavior).toBeTypeOf("string");
      expect(["low", "medium", "high"]).toContain(r.expected.risk);
    }
  });
});
