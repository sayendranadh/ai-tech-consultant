import { describe, it, expect } from "vitest";
import { openDb } from "../src/persistence/db.js";
import { Dao } from "../src/persistence/dao.js";
import { ReviewService, HIGH_RISK_EXCLUSIONS_DEFAULT } from "../src/review/service.js";
import { SimulatedDeliveryAdapter } from "../src/autonomy/delivery.js";
import { createHash } from "node:crypto";

function seedOne(db: ReturnType<typeof openDb>, category: string, reply = "x") {
  const dao = new Dao(db);
  const email_id = `e-${Math.random().toString(36).slice(2, 8)}`;
  dao.insertEmail({ email_id, subject: "S", body: "B", received_at: new Date().toISOString() });
  const draft_id = dao.insertDraft(email_id, {
    email_id, predicted_category: category as any, urgency: "normal", risk: "low",
    request_summary: "s", draft_reply: reply, supporting_sources: [],
    insufficient_evidence: false, escalation_required: false, human_approval_required: true,
    recommended_next_action: "reply", model_id: "m", prompt_version: "p",
  }, `idem-${email_id}`, createHash("sha256").update(reply).digest("hex"));
  return { dao, draft_id, email_id };
}

describe("feedback records", () => {
  it("approvals persist final reply, correction reason, delivery id", async () => {
    const db = openDb(":memory:");
    const { dao, draft_id } = seedOne(db, "how_to");
    const svc = new ReviewService(dao, new SimulatedDeliveryAdapter(), db);
    const r = await svc.apply({
      draft_id, action: "approve", reviewer: "reviewer-1",
      delivery_target: "c@e.com", correction_reason: "minor tone change",
      exclusion_list: HIGH_RISK_EXCLUSIONS_DEFAULT,
    });
    const rows = dao.listApprovalsForDraft(draft_id);
    expect(rows).toHaveLength(1);
    const row = rows[0]!;
    expect(row.decision).toBe("approve");
    expect(row.reviewer).toBe("reviewer-1");
    expect(row.correction_reason).toBe("minor tone change");
    expect(row.delivery_id).toBe(r.delivery_id);
  });

  it("repeated corrections query groups by (category, reason)", async () => {
    const db = openDb(":memory:");
    const svc = new ReviewService(new Dao(db), new SimulatedDeliveryAdapter(), db);
    for (let i = 0; i < 3; i++) {
      const { draft_id } = seedOne(db, "how_to");
      await svc.apply({ draft_id, action: "edit", edited_text: "fixed", reviewer: "r", delivery_target: "c@e.com", correction_reason: "tone", exclusion_list: HIGH_RISK_EXCLUSIONS_DEFAULT });
    }
    const dao = new Dao(db);
    const results = dao.repeatedCorrections(10);
    expect(results.some((r) => r.category === "how_to" && r.correction_reason === "tone" && r.count === 3)).toBe(true);
  });
});
