import { describe, it, expect } from "vitest";
import { openDb } from "../src/persistence/db.js";
import { Dao } from "../src/persistence/dao.js";
import type { DraftBody } from "../src/pipeline/draft.js";
import { idempotencyKey } from "../src/kb/idempotency.js";

const body: DraftBody = {
  email_id: "e1",
  predicted_category: "how_to",
  urgency: "normal",
  risk: "low",
  request_summary: "s",
  draft_reply: "r",
  supporting_sources: [],
  insufficient_evidence: false,
  escalation_required: false,
  human_approval_required: true,
  recommended_next_action: "reply",
  model_id: "m",
  prompt_version: "p",
};

describe("idempotent draft insert", () => {
  it("returns the same draft_id on repeated insert with same key", () => {
    const dao = new Dao(openDb(":memory:"));
    dao.insertEmail({ email_id: "e1", subject: "S", body: "B", received_at: new Date().toISOString() });
    const key = idempotencyKey("e1", "v1");
    const id1 = dao.insertDraft("e1", body, key, "h1");
    const id2 = dao.insertDraft("e1", body, key, "h1");
    expect(id1).toBe(id2);
  });

  it("different pipeline version produces different draft_id", () => {
    const dao = new Dao(openDb(":memory:"));
    dao.insertEmail({ email_id: "e1", subject: "S", body: "B", received_at: new Date().toISOString() });
    const id1 = dao.insertDraft("e1", body, idempotencyKey("e1", "v1"), "h1");
    const id2 = dao.insertDraft("e1", body, idempotencyKey("e1", "v2"), "h1");
    expect(id1).not.toBe(id2);
  });
});
