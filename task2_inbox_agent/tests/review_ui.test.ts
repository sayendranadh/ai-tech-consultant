import { describe, it, expect } from "vitest";
import { renderPendingList, renderDraftDetail } from "../src/review/html.js";
import { renderTriggerForm } from "../src/review/trigger_html.js";

describe("review HTML", () => {
  it("pending list includes drafts", () => {
    const html = renderPendingList([]);
    expect(html).toContain("Pending drafts");
  });

  it("draft detail shows warnings when insufficient_evidence", () => {
    const html = renderDraftDetail({
      draft: {
        draft_id: "d1", email_id: "e1", idempotency_key: "k", category: "how_to",
        urgency: "normal", risk: "low", request_summary: "s", draft_reply: "r",
        supporting_sources_json: "[]", insufficient_evidence: 1, escalation_required: 0,
        human_approval_required: 1, recommended_next_action: "reply",
        model_id: "m", prompt_version: "p", draft_hash: "h", generated_at: "now", approval_status: "pending",
      },
      email: { subject: "S", body: "B" },
      sources: [],
      approvals: [],
      counter: null,
      exclusion_list: ["refund_cancellation", "complaint"],
    });
    expect(html).toContain("INSUFFICIENT EVIDENCE");
  });
});

describe("Trigger form", () => {
  it("renders a form with email_id, subject, body fields", () => {
    const html = renderTriggerForm();
    expect(html).toContain('name="email_id"');
    expect(html).toContain('name="subject"');
    expect(html).toContain('name="body"');
    expect(html).toContain("Process email");
  });

  it("has a status banner element for error rendering", () => {
    const html = renderTriggerForm();
    expect(html).toContain('id="status-banner"');
  });
});
