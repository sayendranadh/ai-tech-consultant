import { randomUUID } from "node:crypto";
import type { DB } from "./db.js";
import type { DraftBody } from "../pipeline/draft.js";
import type { DeliveryResult } from "../autonomy/delivery.js";

function nowIso(): string {
  return new Date().toISOString();
}

export interface InsertEmail {
  email_id: string;
  subject: string;
  body: string;
  thread_context?: string;
  received_at: string;
  is_synthetic?: boolean;
}

export interface DraftRow {
  draft_id: string;
  email_id: string;
  idempotency_key: string;
  category: string;
  urgency: string;
  risk: string;
  request_summary: string;
  draft_reply: string;
  supporting_sources_json: string;
  insufficient_evidence: number;
  escalation_required: number;
  human_approval_required: number;
  recommended_next_action: string;
  model_id: string;
  prompt_version: string;
  draft_hash: string;
  generated_at: string;
  approval_status: string;
}

export class Dao {
  constructor(readonly db: DB) {}

  insertEmail(e: InsertEmail): void {
    this.db
      .prepare(
        `INSERT OR IGNORE INTO emails (email_id, subject, body, thread_context, is_synthetic, received_at, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(e.email_id, e.subject, e.body, e.thread_context ?? null, e.is_synthetic === false ? 0 : 1, e.received_at, nowIso());
  }

  getEmail(emailId: string): { email_id: string; subject: string; body: string; thread_context: string | null } | undefined {
    return this.db
      .prepare(`SELECT email_id, subject, body, thread_context FROM emails WHERE email_id = ?`)
      .get(emailId) as { email_id: string; subject: string; body: string; thread_context: string | null } | undefined;
  }

  insertDraft(emailId: string, body: DraftBody, idempotencyKey: string, draftHash: string): string {
    if (body.email_id !== emailId) {
      throw new Error(`Dao.insertDraft: body.email_id="${body.email_id}" does not match emailId="${emailId}"`);
    }
    const existing = this.db
      .prepare(`SELECT draft_id FROM drafts WHERE idempotency_key = ?`)
      .get(idempotencyKey) as { draft_id: string } | undefined;
    if (existing) return existing.draft_id;

    const draft_id = randomUUID();
    this.db
      .prepare(
        `INSERT INTO drafts (
          draft_id, email_id, idempotency_key, category, urgency, risk, request_summary, draft_reply,
          supporting_sources_json, insufficient_evidence, escalation_required, human_approval_required,
          recommended_next_action, model_id, prompt_version, draft_hash, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        draft_id,
        emailId,
        idempotencyKey,
        body.predicted_category,
        body.urgency,
        body.risk,
        body.request_summary,
        body.draft_reply,
        JSON.stringify(body.supporting_sources),
        body.insufficient_evidence ? 1 : 0,
        body.escalation_required ? 1 : 0,
        body.human_approval_required ? 1 : 0,
        body.recommended_next_action,
        body.model_id,
        body.prompt_version,
        draftHash,
        nowIso(),
      );
    return draft_id;
  }

  getDraft(draftId: string): DraftRow | undefined {
    return this.db.prepare(`SELECT * FROM drafts WHERE draft_id = ?`).get(draftId) as DraftRow | undefined;
  }

  listPendingDrafts(limit = 100): DraftRow[] {
    return this.db
      .prepare(`SELECT * FROM drafts WHERE approval_status = 'pending' ORDER BY generated_at ASC LIMIT ?`)
      .all(limit) as DraftRow[];
  }

  insertDelivery(input: { draft_id: string; result: DeliveryResult }): string {
    this.db
      .prepare(
        `INSERT INTO deliveries (delivery_id, draft_id, mode, delivered_text, is_simulated, delivery_status, error, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        input.result.delivery_id,
        input.draft_id,
        input.result.mode,
        input.result.delivered_text,
        input.result.is_simulated ? 1 : 0,
        input.result.delivery_status,
        input.result.error ?? null,
        nowIso(),
      );
    return input.result.delivery_id;
  }

  getDelivery(deliveryId: string): Record<string, unknown> | undefined {
    return this.db.prepare(`SELECT * FROM deliveries WHERE delivery_id = ?`).get(deliveryId) as Record<string, unknown> | undefined;
  }

  insertApproval(input: {
    draft_id: string;
    decision: "approve" | "edit" | "reject" | "escalate";
    final_reply?: string | undefined;
    correction_reason?: string | undefined;
    reviewer: string;
    delivery_id?: string | undefined;
    is_qualifying?: boolean | undefined;
  }): string {
    const approval_id = randomUUID();
    this.db
      .prepare(
        `INSERT INTO approvals (approval_id, draft_id, decision, final_reply, correction_reason, reviewer, approved_at, delivery_id, is_qualifying)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        approval_id,
        input.draft_id,
        input.decision,
        input.final_reply ?? null,
        input.correction_reason ?? null,
        input.reviewer,
        nowIso(),
        input.delivery_id ?? null,
        input.is_qualifying ? 1 : 0,
      );
    const status =
      input.decision === "approve" ? "approved" : input.decision === "edit" ? "edited" : input.decision === "reject" ? "rejected" : "escalated";
    this.db.prepare(`UPDATE drafts SET approval_status = ? WHERE draft_id = ?`).run(status, input.draft_id);
    return approval_id;
  }

  listApprovalsForDraft(draftId: string): Array<Record<string, unknown>> {
    return this.db
      .prepare(`SELECT * FROM approvals WHERE draft_id = ? ORDER BY approved_at ASC`)
      .all(draftId) as Array<Record<string, unknown>>;
  }

  repeatedCorrections(limit: number): Array<{ category: string; correction_reason: string; count: number }> {
    return this.db
      .prepare(
        `SELECT d.category AS category, a.correction_reason AS correction_reason, COUNT(*) AS count
         FROM approvals a JOIN drafts d ON d.draft_id = a.draft_id
         WHERE a.correction_reason IS NOT NULL AND a.correction_reason != ''
         GROUP BY d.category, a.correction_reason
         ORDER BY count DESC LIMIT ?`,
      )
      .all(limit) as Array<{ category: string; correction_reason: string; count: number }>;
  }
}
