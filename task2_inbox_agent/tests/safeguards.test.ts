import { describe, it, expect } from "vitest";
import { detectUnauthorizedCommitments } from "../src/pipeline/safeguards.js";
import type { DraftBody } from "../src/pipeline/draft.js";

const base: DraftBody = {
  email_id: "e1",
  predicted_category: "refund_cancellation",
  urgency: "high",
  risk: "high",
  request_summary: "s",
  draft_reply: "We will refund your full amount by Friday.",
  supporting_sources: [],
  insufficient_evidence: false,
  escalation_required: true,
  human_approval_required: true,
  recommended_next_action: "escalate",
  model_id: "m",
  prompt_version: "p",
};

describe("safeguards detect unauthorized commitments", () => {
  it("flags refund and date promises", () => {
    const findings = detectUnauthorizedCommitments(base, false, false);
    const kinds = findings.map((f) => f.kind);
    expect(kinds).toContain("refund");
    expect(kinds).toContain("delivery_date");
  });
  it("is silent when evidence AND authorization are present", () => {
    const findings = detectUnauthorizedCommitments(base, true, true);
    expect(findings).toHaveLength(0);
  });
});
