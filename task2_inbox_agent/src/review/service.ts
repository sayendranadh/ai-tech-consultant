import type { Dao } from "../persistence/dao.js";
import type { DeliveryAdapter } from "../autonomy/delivery.js";
import type { DB } from "../persistence/db.js";
import { recordQualifyingEvent, AUTONOMY_THRESHOLD } from "../autonomy/state_machine.js";

export const HIGH_RISK_EXCLUSIONS_DEFAULT = ["refund_cancellation", "complaint"];

export interface ReviewDecisionInput {
  draft_id: string;
  action: "approve" | "edit" | "reject" | "escalate";
  edited_text?: string | undefined;
  replacement_text?: string | undefined;
  correction_reason?: string | undefined;
  reviewer: string;
  delivery_target: string;
  exclusion_list?: string[] | undefined;
}

export interface ReviewDecisionResult {
  approval_id: string;
  delivery_id: string | null;
  qualifying: boolean | null;
  disqualified_reason: string | null;
  new_count: number | null;
  eligible_for_autonomy: boolean | null;
  simulated: boolean;
}

export class ReviewService {
  constructor(private readonly dao: Dao, private readonly adapter: DeliveryAdapter, private readonly db: DB) {}

  async apply(input: ReviewDecisionInput): Promise<ReviewDecisionResult> {
    const draft = this.dao.getDraft(input.draft_id);
    if (!draft) throw new Error(`draft not found: ${input.draft_id}`);

    const exclusion_list = input.exclusion_list ?? HIGH_RISK_EXCLUSIONS_DEFAULT;

    if (input.action === "escalate") {
      const approval_id = this.dao.insertApproval({
        draft_id: input.draft_id,
        decision: "escalate",
        correction_reason: input.correction_reason,
        reviewer: input.reviewer,
      });
      const res = recordQualifyingEvent(this.db, {
        category: draft.category,
        draft_id: input.draft_id,
        delivery_id: "none",
        generated_draft: draft.draft_reply,
        final_draft: draft.draft_reply,
        delivery_status: "failed",
        exclusion_list,
        disqualifying_reason: "escalated",
      });
      return {
        approval_id,
        delivery_id: null,
        qualifying: false,
        disqualified_reason: "escalated",
        new_count: res.new_count,
        eligible_for_autonomy: res.eligible_for_autonomy,
        simulated: false,
      };
    }

    if (input.action === "reject") {
      if (!input.replacement_text || !input.replacement_text.trim()) {
        throw new Error("reject requires replacement_text");
      }
      const approval_id = this.dao.insertApproval({
        draft_id: input.draft_id,
        decision: "reject",
        final_reply: input.replacement_text,
        correction_reason: input.correction_reason,
        reviewer: input.reviewer,
      });
      const res = recordQualifyingEvent(this.db, {
        category: draft.category,
        draft_id: input.draft_id,
        delivery_id: "none",
        generated_draft: draft.draft_reply,
        final_draft: draft.draft_reply,
        delivery_status: "failed",
        exclusion_list,
        disqualifying_reason: "rejected",
      });
      return {
        approval_id,
        delivery_id: null,
        qualifying: false,
        disqualified_reason: "rejected",
        new_count: res.new_count,
        eligible_for_autonomy: res.eligible_for_autonomy,
        simulated: false,
      };
    }

    const text = input.action === "edit" ? input.edited_text ?? "" : draft.draft_reply;
    if (!text.trim()) throw new Error("delivery text must be non-empty");

    const delivery_result = await this.adapter.deliver({
      draft_id: input.draft_id,
      to: input.delivery_target,
      text,
    });
    const delivery_id = this.dao.insertDelivery({ draft_id: input.draft_id, result: delivery_result });

    const disqualifying_reason =
      input.action === "edit"
        ? "edited_by_reviewer"
        : delivery_result.delivery_status === "failed"
        ? "delivery_failed"
        : undefined;

    const qual = recordQualifyingEvent(this.db, {
      category: draft.category,
      draft_id: input.draft_id,
      delivery_id,
      generated_draft: draft.draft_reply,
      final_draft: text,
      delivery_status: delivery_result.delivery_status === "simulated_sent" ? "simulated_sent" : delivery_result.delivery_status,
      exclusion_list,
      disqualifying_reason,
    });

    const approval_id = this.dao.insertApproval({
      draft_id: input.draft_id,
      decision: input.action === "approve" ? "approve" : "edit",
      final_reply: text,
      correction_reason: input.correction_reason,
      reviewer: input.reviewer,
      delivery_id,
      is_qualifying: qual.qualified,
    });

    return {
      approval_id,
      delivery_id,
      qualifying: qual.qualified,
      disqualified_reason: qual.disqualified_reason,
      new_count: qual.new_count,
      eligible_for_autonomy: qual.eligible_for_autonomy,
      simulated: delivery_result.is_simulated,
    };
  }
}

void AUTONOMY_THRESHOLD;
