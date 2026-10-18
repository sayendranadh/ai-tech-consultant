import { z } from "zod";
import { CategorySchema, UrgencySchema, RiskSchema } from "./classify.js";

export const DraftBodySchema = z.object({
  email_id: z.string(),
  predicted_category: CategorySchema,
  urgency: UrgencySchema,
  risk: RiskSchema,
  request_summary: z.string().min(1),
  draft_reply: z.string().min(1),
  supporting_sources: z.array(
    z.object({
      url: z.string(),
      section: z.string().nullable(),
      chunk_id: z.number().int(),
      title: z.string().nullable(),
    }),
  ),
  insufficient_evidence: z.boolean(),
  escalation_required: z.boolean(),
  human_approval_required: z.boolean(),
  recommended_next_action: z.enum(["reply", "ask_clarification", "escalate", "reject"]),
  model_id: z.string(),
  prompt_version: z.string(),
});
export type DraftBody = z.infer<typeof DraftBodySchema>;

export interface Drafter {
  readonly model_id: string;
  readonly prompt_version: string;
  draft(input: {
    email: { subject: string; body: string; thread_context?: string };
    classification: { category: string; urgency: string; risk: string; summary: string };
    kbAnswer?: {
      status: "answered" | "insufficient_evidence" | "failed";
      answer: string;
      sources: Array<{ url: string; section: string | null; chunk_id: number; title: string | null }>;
      escalation_required: boolean;
    };
  }): Promise<DraftBody>;
}

export class MockDrafter implements Drafter {
  readonly model_id = "mock-drafter/v1";
  readonly prompt_version = "mock-v1";
  constructor(private readonly table: Record<string, DraftBody>) {}
  async draft(input: Parameters<Drafter["draft"]>[0]): Promise<DraftBody> {
    const key = `${input.email.subject}\n${input.email.body}`;
    const hit = this.table[key];
    if (!hit) throw new Error(`MockDrafter has no fixture for input: ${key.slice(0, 60)}...`);
    return hit;
  }
}

import { UnconfiguredModelError } from "./classify.js";

import Anthropic from "@anthropic-ai/sdk";
import type { AnthropicClientLike } from "./classify.js";

function buildDefaultClient(apiKey: string): AnthropicClientLike {
  return new Anthropic({ apiKey }) as unknown as AnthropicClientLike;
}

export const SYSTEM_PROMPT = `You draft customer support replies.

Rules:
- Use ONLY the evidence provided in the KB answer. Do not invent product claims.
- If the KB status is "insufficient_evidence" or "failed", do NOT answer the
  substantive question — but you MUST still write a short holding reply.
  Fill draft_reply with 1-3 sentences that acknowledge the request and state
  it is being escalated to a specialist. Do not make factual claims and do
  not cite chunk_ids in a holding reply. Set insufficient_evidence=true and
  escalation_required=true.
- draft_reply is REQUIRED and MUST NEVER be empty. request_summary is also
  REQUIRED and MUST NEVER be empty — always one sentence describing the ask.
- For refund, price, delivery date, or feature delivery promises: set escalation_required=true and do not make the promise.
- Every factual claim must correspond to a source in the provided sources list.
- Cite chunk_ids in the reply as [chunk_id=N].
- Keep draft_reply under 200 words. Use at most 3 supporting sources.
- Do not include full URLs in the draft_reply text; the supporting_sources array carries the URLs. Do not restate the URL after the citation marker.

Return ONLY a JSON object with this exact shape:
{"draft_reply": "<the reply text — ALWAYS non-empty>",
 "request_summary": "<one sentence summary — ALWAYS non-empty>",
 "supporting_sources": [{"chunk_id": N, "url": "<url>", "section": "<section or null>", "title": "<title or null>"}],
 "insufficient_evidence": true|false,
 "escalation_required": true|false,
 "recommended_next_action": "reply|ask_clarification|escalate|reject"}

No prose outside the JSON.`;

export class ClaudeDrafter implements Drafter {
  readonly model_id: string;
  readonly prompt_version: string;
  private readonly client: AnthropicClientLike;

  constructor(
    private readonly apiKey: string,
    modelId: string,
    promptVersion: string,
    client?: AnthropicClientLike,
  ) {
    if (!apiKey || !modelId) {
      throw new UnconfiguredModelError(
        "ClaudeDrafter requires ANTHROPIC_API_KEY and CLAUDE_DRAFTER_MODEL",
      );
    }
    this.model_id = modelId;
    this.prompt_version = promptVersion;
    if (client) {
      this.client = client;
    } else {
      this.client = buildDefaultClient(apiKey);
    }
  }

  async draft(input: Parameters<Drafter["draft"]>[0]): Promise<DraftBody> {
    const kb = input.kbAnswer;
    const kbSection = kb
      ? `\n\nKB STATUS: ${kb.status}\nKB ANSWER:\n${kb.answer}\nKB SOURCES: ${JSON.stringify(kb.sources)}\nKB ESCALATION_REQUIRED: ${kb.escalation_required}`
      : "\n\nKB STATUS: not_queried";
    const user = `EMAIL SUBJECT:\n${input.email.subject}\n\nEMAIL BODY:\n${input.email.body}\n\nCLASSIFICATION:\n${JSON.stringify(input.classification)}${kbSection}`;

    const resp = await this.client.messages.create({
      model: this.model_id,
      max_tokens: 2500,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: user }],
    });

    const raw = resp.content
      .filter((b) => b.type === "text" && typeof b.text === "string")
      .map((b) => b.text as string)
      .join("")
      .trim();

    const parsed = this.parseJson(raw);
    if (!parsed) {
      throw new Error("ClaudeDrafter: model response was not valid JSON");
    }

    const combined = {
      email_id: "", // filled by caller? no — the harness uses the real email id. We accept whatever the pipeline passes.
      predicted_category: input.classification.category,
      urgency: input.classification.urgency,
      risk: input.classification.risk,
      request_summary: parsed.request_summary,
      draft_reply: parsed.draft_reply,
      supporting_sources: Array.isArray(parsed.supporting_sources) ? parsed.supporting_sources : [],
      insufficient_evidence: Boolean(parsed.insufficient_evidence),
      escalation_required: Boolean(parsed.escalation_required),
      human_approval_required: true,
      recommended_next_action: parsed.recommended_next_action,
      model_id: this.model_id,
      prompt_version: this.prompt_version,
    };
    const validated = DraftBodySchema.safeParse(combined);
    if (!validated.success) {
      throw new Error(
        `ClaudeDrafter: model response did not match schema: ${validated.error.message}`,
      );
    }
    return validated.data;
  }

  private parseJson(raw: string): Record<string, unknown> | null {
    let text = raw;
    if (text.startsWith("```")) {
      text = text
        .split("\n")
        .filter((l) => !l.trim().startsWith("```"))
        .join("\n");
    }
    const trimmed = text.trim();
    // Detect truncation: a well-formed response ends with a closing brace.
    if (!trimmed.endsWith("}")) {
      // eslint-disable-next-line no-console
      console.error(
        `[ClaudeDrafter] Response appears truncated (does not end with '}'). ` +
        `Length: ${raw.length}. Consider raising max_tokens.`,
      );
      return null;
    }
    const start = trimmed.indexOf("{");
    const end = trimmed.lastIndexOf("}");
    if (start === -1 || end === -1 || end <= start) return null;
    try {
      return JSON.parse(trimmed.slice(start, end + 1)) as Record<string, unknown>;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(`[ClaudeDrafter] JSON parse failed: ${err}. Response length: ${raw.length}`);
      return null;
    }
  }
}
