import { describe, it, expect } from "vitest";
import { PipelineRunner } from "../src/pipeline/runner.js";
import { MockClassifier } from "../src/pipeline/classify.js";
import { MockDrafter, type DraftBody } from "../src/pipeline/draft.js";
import { KBClient } from "../src/kb/client.js";
import { openDb } from "../src/persistence/db.js";
import { Dao } from "../src/persistence/dao.js";

function freshDao(): Dao {
  return new Dao(openDb(":memory:"));
}

async function runWithKbFailure() {
  const dao = freshDao();
  const emailId = "e1";
  const subject = "S";
  const body = "B";
  dao.insertEmail({ email_id: emailId, subject, body, received_at: new Date().toISOString() });

  const key = `${subject}\n${body}`;

  const classifier = new MockClassifier({
    [key]: {
      category: "how_to",
      urgency: "normal",
      risk: "low",
      summary: "s",
      rationale: "r",
      model_id: "mock-classifier/v1",
      prompt_version: "mock-v1",
    },
  });

  const draftFixture: DraftBody = {
    email_id: emailId,
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
    model_id: "mock-drafter/v1",
    prompt_version: "mock-v1",
  };

  const drafter = new MockDrafter({ [key]: draftFixture });

  const kb = new KBClient({
    baseUrl: "http://kb",
    bearerToken: "tok",
    timeoutMs: 1000,
    maxRetries: 0,
    backoffBaseMs: 1,
    fetchImpl: (async () => {
      throw new Error("network down");
    }) as unknown as typeof fetch,
  });

  const runner = new PipelineRunner({ dao, classifier, drafter, kb, pipelineVersion: "v-test" });
  return runner.processEmail(emailId);
}

describe("pipeline behavior when KB unavailable", () => {
  it("forces insufficient_evidence and escalation_required", async () => {
    const result = await runWithKbFailure();
    expect(result.body.insufficient_evidence).toBe(true);
    expect(result.body.escalation_required).toBe(true);
    expect(result.body.human_approval_required).toBe(true);
  });
});
