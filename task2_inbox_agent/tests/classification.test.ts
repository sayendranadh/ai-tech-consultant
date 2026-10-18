import { describe, it, expect } from "vitest";
import { MockClassifier } from "../src/pipeline/classify.js";
import { loadMockFixtures } from "../src/fixtures/loader.js";

const fixtures = loadMockFixtures();

describe("mock classifier", () => {
  it("returns the fixture for a known email", async () => {
    const c = new MockClassifier(fixtures.classifications);
    const k = Object.keys(fixtures.classifications)[0]!;
    const [subject, body] = k.split("\n") as [string, string];
    const r = await c.classify({ subject, body });
    expect(r.category).toBeDefined();
    expect(r.risk).toBeDefined();
  });

  it("throws on unknown email", async () => {
    const c = new MockClassifier({});
    await expect(c.classify({ subject: "nope", body: "nope" })).rejects.toThrow();
  });
});
