import { describe, it, expect } from "vitest";
import { ClaudeClassifier, UnconfiguredModelError } from "../src/pipeline/classify.js";

function fakeClient(text: string) {
  return {
    messages: {
      create: async () => ({ content: [{ type: "text", text }] }),
    },
  };
}

describe("ClaudeClassifier", () => {
  it("throws UnconfiguredModelError with no api key", () => {
    expect(() => new ClaudeClassifier("", "m", "v1", fakeClient("{}"))).toThrow(UnconfiguredModelError);
  });

  it("throws UnconfiguredModelError with no model", () => {
    expect(() => new ClaudeClassifier("k", "", "v1", fakeClient("{}"))).toThrow(UnconfiguredModelError);
  });

  it("parses a valid JSON response", async () => {
    const body = JSON.stringify({
      category: "how_to",
      urgency: "normal",
      risk: "low",
      summary: "Customer asks how to reset password.",
      rationale: "Simple how-to, low risk.",
    });
    const c = new ClaudeClassifier("k", "claude-haiku-5-5", "v1", fakeClient(body));
    const result = await c.classify({ subject: "Reset password", body: "How?" });
    expect(result.category).toBe("how_to");
    expect(result.model_id).toBe("claude-haiku-5-5");
    expect(result.prompt_version).toBe("v1");
  });

  it("strips markdown code fences", async () => {
    const inner = JSON.stringify({
      category: "complaint",
      urgency: "high",
      risk: "high",
      summary: "Frustrated customer.",
      rationale: "High-risk complaint.",
    });
    const fenced = "```json\n" + inner + "\n```";
    const c = new ClaudeClassifier("k", "m", "v1", fakeClient(fenced));
    const result = await c.classify({ subject: "S", body: "B" });
    expect(result.category).toBe("complaint");
  });

  it("throws on invalid category", async () => {
    const body = JSON.stringify({
      category: "not_a_category",
      urgency: "normal",
      risk: "low",
      summary: "s",
      rationale: "r",
    });
    const c = new ClaudeClassifier("k", "m", "v1", fakeClient(body));
    await expect(c.classify({ subject: "S", body: "B" })).rejects.toThrow(/did not match schema/);
  });

  it("throws on unparseable response", async () => {
    const c = new ClaudeClassifier("k", "m", "v1", fakeClient("Not JSON"));
    await expect(c.classify({ subject: "S", body: "B" })).rejects.toThrow(/not valid JSON/);
  });
});
