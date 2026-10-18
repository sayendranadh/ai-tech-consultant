import { createHash } from "node:crypto";
import type { KBClient } from "../kb/client.js";
import { KBUnavailableError } from "../kb/client.js";
import type { Classifier } from "./classify.js";
import type { Drafter, DraftBody } from "./draft.js";
import { DraftBodySchema } from "./draft.js";
import { idempotencyKey } from "../kb/idempotency.js";
import type { Dao } from "../persistence/dao.js";

export interface RunnerDeps {
  dao: Dao;
  classifier: Classifier;
  drafter: Drafter;
  kb: KBClient;
  pipelineVersion: string;
}

export interface RunnerResult {
  draft_id: string;
  body: DraftBody;
  existing: boolean;
}

export class PipelineRunner {
  constructor(private readonly deps: RunnerDeps) {}

  async processEmail(emailId: string): Promise<RunnerResult> {
    const email = this.deps.dao.getEmail(emailId);
    if (!email) throw new Error(`email not found: ${emailId}`);

    const idemKey = idempotencyKey(emailId, this.deps.pipelineVersion);

    const classifyInput: { subject: string; body: string; thread_context?: string } = {
      subject: email.subject,
      body: email.body,
    };
    if (email.thread_context !== null && email.thread_context !== undefined) {
      classifyInput.thread_context = email.thread_context;
    }

    const classification = await this.deps.classifier.classify(classifyInput);

    let kbAnswer: Awaited<ReturnType<KBClient["query"]>> | undefined = undefined;
    let kbUnavailable = false;
    try {
      kbAnswer = await this.deps.kb.query({ question: `${email.subject}\n\n${email.body}` });
    } catch (err) {
      if (err instanceof KBUnavailableError) {
        kbUnavailable = true;
      } else {
        throw err;
      }
    }

    const draftInput: Parameters<Drafter["draft"]>[0] = {
      email: classifyInput,
      classification,
    };
    if (kbAnswer) {
      draftInput.kbAnswer = {
        status: kbAnswer.status,
        answer: kbAnswer.answer,
        sources: kbAnswer.sources.map((s) => ({ url: s.url, section: s.section, chunk_id: s.chunk_id, title: s.title })),
        escalation_required: kbAnswer.escalation_required,
      };
    }

    const draftBody = await this.deps.drafter.draft(draftInput);

    // Live drafters (ClaudeDrafter) do not receive the emailId in their input, so
    // they return an empty email_id. Fill it in here before the match check.
    // A malicious or buggy drafter that returns a different non-empty id will still
    // fail the check below, preserving the guard.
    if (draftBody.email_id === "" || draftBody.email_id === undefined) {
      draftBody.email_id = emailId;
    }

    if (draftBody.email_id !== emailId) {
      throw new Error(
        `drafter returned email_id "${draftBody.email_id}" but pipeline is processing "${emailId}"; fixtures must match dataset ids`,
      );
    }

    const validated = DraftBodySchema.parse({
      ...draftBody,
      email_id: emailId,
      insufficient_evidence: kbUnavailable ? true : draftBody.insufficient_evidence,
      escalation_required: kbUnavailable ? true : draftBody.escalation_required,
      human_approval_required: true,
    });

    const draftHash = createHash("sha256").update(validated.draft_reply).digest("hex");
    const draftId = this.deps.dao.insertDraft(emailId, validated, idemKey, draftHash);
    return { draft_id: draftId, body: validated, existing: false };
  }
}
