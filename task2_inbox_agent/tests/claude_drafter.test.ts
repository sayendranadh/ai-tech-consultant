import { describe, it, expect } from "vitest";
import { ClaudeDrafter } from "../src/pipeline/draft.js";
import { ClassificationSchema, UnconfiguredModelError } from "../src/pipeline/classify.js";

function fakeClient(text: string) {
  return {
    messages: {
      create: async () => ({ content: [{ type: "text", text }] }),
    },
  };
}

const CLASSIFICATION = ClassificationSchema.parse({
  category: "how_to",
  urgency: "normal",
  risk: "low",
  summary: "Customer needs help resetting password.",
  rationale: "Simple how-to.",
  model_id: "claude-haiku-5-5",
  prompt_version: "v1",
});

describe("ClaudeDrafter", () => {
  it("throws UnconfiguredModelError with no api key", () => {
    expect(() => new ClaudeDrafter("", "m", "v1", fakeClient("{}"))).toThrow(UnconfiguredModelError);
  });

  it("throws UnconfiguredModelError with no model", () => {
    expect(() => new ClaudeDrafter("k", "", "v1", fakeClient("{}"))).toThrow(UnconfiguredModelError);
  });

  it("parses a valid response with KB evidence", async () => {
    const body = JSON.stringify({
      request_summary: "Customer asks how to reset password.",
      draft_reply: "You can reset your password from the login page. [chunk_id=1]",
      supporting_sources: [
        { chunk_id: 1, url: "https://support.example/reset", section: "Account", title: "Reset" },
      ],
      insufficient_evidence: false,
      escalation_required: false,
      recommended_next_action: "reply",
    });
    const d = new ClaudeDrafter("k", "claude-haiku-5-5", "v1", fakeClient(body));
    const result = await d.draft({
      email: { subject: "Reset", body: "How to reset?" },
      classification: CLASSIFICATION,
      kbAnswer: {
        status: "answered",
        answer: "Use the login page.",
        sources: [{ chunk_id: 1, url: "https://support.example/reset", section: "Account", title: "Reset" }],
        escalation_required: false,
      },
    });
    expect(result.draft_reply).toContain("[chunk_id=1]");
    expect(result.supporting_sources.length).toBe(1);
    expect(result.human_approval_required).toBe(true);
    expect(result.model_id).toBe("claude-haiku-5-5");
  });

  it("parses a response with insufficient evidence", async () => {
    const body = JSON.stringify({
      request_summary: "Unsupported question.",
      draft_reply: "I don't have information about that.",
      supporting_sources: [],
      insufficient_evidence: true,
      escalation_required: true,
      recommended_next_action: "escalate",
    });
    const d = new ClaudeDrafter("k", "m", "v1", fakeClient(body));
    const result = await d.draft({
      email: { subject: "S", body: "B" },
      classification: CLASSIFICATION,
    });
    expect(result.insufficient_evidence).toBe(true);
    expect(result.escalation_required).toBe(true);
  });

  it("rejects a response with no request_summary", async () => {
    const body = JSON.stringify({
      draft_reply: "Reply",
      supporting_sources: [],
      insufficient_evidence: false,
      escalation_required: false,
      recommended_next_action: "reply",
    });
    const d = new ClaudeDrafter("k", "m", "v1", fakeClient(body));
    await expect(
      d.draft({ email: { subject: "S", body: "B" }, classification: CLASSIFICATION }),
    ).rejects.toThrow(/did not match schema/);
  });

  it("rejects invalid recommended_next_action", async () => {
    const body = JSON.stringify({
      request_summary: "s",
      draft_reply: "r",
      supporting_sources: [],
      insufficient_evidence: false,
      escalation_required: false,
      recommended_next_action: "promise_refund",
    });
    const d = new ClaudeDrafter("k", "m", "v1", fakeClient(body));
    await expect(
      d.draft({ email: { subject: "S", body: "B" }, classification: CLASSIFICATION }),
    ).rejects.toThrow(/did not match schema/);
  });
});

describe("ClaudeDrafter — truncation detection", () => {
  it("rejects a truncated response with a clear error", async () => {
    // Simulates a response that was cut off mid-JSON (max_tokens exhaustion)
    const truncated = '{"draft_reply": "Hi, thanks for reaching out. [chunk_id=1]';
    const d = new ClaudeDrafter("k", "m", "v1", fakeClient(truncated));
    await expect(
      d.draft({
        email: { subject: "S", body: "B" },
        classification: CLASSIFICATION,
      }),
    ).rejects.toThrow(/not valid JSON/);
  });

  it("accepts a well-formed JSON response that ends with }", async () => {
    const body = JSON.stringify({
      request_summary: "s",
      draft_reply: "r",
      supporting_sources: [],
      insufficient_evidence: false,
      escalation_required: false,
      recommended_next_action: "reply",
    });
    const d = new ClaudeDrafter("k", "m", "v1", fakeClient(body));
    const result = await d.draft({
      email: { subject: "S", body: "B" },
      classification: CLASSIFICATION,
    });
    expect(result.draft_reply).toBe("r");
  });
});
