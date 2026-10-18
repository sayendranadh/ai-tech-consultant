import type { DB } from "../persistence/db.js";
import { draftsEqual, hashText } from "./compare.js";

export const AUTONOMY_THRESHOLD = 20;

export interface QualifyingInput {
  category: string;
  draft_id: string;
  delivery_id: string;
  generated_draft: string;
  final_draft: string;
  delivery_status: "delivered" | "failed" | "simulated_sent";
  exclusion_list: string[];
  disqualifying_reason?: string | undefined;
}

export interface QualifyingResult {
  qualified: boolean;
  disqualified_reason: string | null;
  new_count: number;
  eligible_for_autonomy: boolean;
  event_id: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

function cryptoRandomId(): string {
  return globalThis.crypto.randomUUID();
}

export function recordQualifyingEvent(db: DB, input: QualifyingInput): QualifyingResult {
  const event_id = cryptoRandomId();
  const ts = nowIso();

  const isExcluded = input.exclusion_list.includes(input.category);
  const deliveredSuccessfully =
    input.delivery_status === "delivered" || input.delivery_status === "simulated_sent";

  let qualified = true;
  let disqualified_reason: string | null = null;

  // Reason ordering: the caller's specific reason wins when supplied.
  if (!deliveredSuccessfully) {
    qualified = false;
    disqualified_reason = input.disqualifying_reason ?? "delivery_not_successful";
  } else if (input.disqualifying_reason) {
    qualified = false;
    disqualified_reason = input.disqualifying_reason;
  } else if (!draftsEqual(input.generated_draft, input.final_draft)) {
    qualified = false;
    disqualified_reason = "draft_edited";
  }

  const genHash = hashText(input.generated_draft);
  const finalHash = hashText(input.final_draft);

  db.prepare(
    `INSERT INTO qualifying_events
      (event_id, category, draft_id, delivery_id, generated_draft_hash, final_draft_hash, qualified, disqualified_reason, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    event_id,
    input.category,
    input.draft_id,
    input.delivery_id,
    genHash,
    finalHash,
    qualified ? 1 : 0,
    disqualified_reason,
    ts,
  );

  const existingQualified = db
    .prepare(
      `SELECT COUNT(*) AS c FROM qualifying_events
       WHERE category = ? AND draft_id = ? AND delivery_id = ? AND qualified = 1`,
    )
    .get(input.category, input.draft_id, input.delivery_id) as { c: number };

  if (existingQualified.c > 1) {
    const cur = getCounter(db, input.category);
    return {
      qualified: false,
      disqualified_reason: "duplicate_event",
      new_count: cur.current_count,
      eligible_for_autonomy: cur.eligible_for_autonomy,
      event_id,
    };
  }

  const row = db
    .prepare(`SELECT * FROM consecutive_approvals WHERE category = ?`)
    .get(input.category) as
    | { current_count: number; eligible_for_autonomy: number; category_history_json: string }
    | undefined;

  let currentCount = row ? row.current_count : 0;
  let eligible = row ? Boolean(row.eligible_for_autonomy) : false;
  const history: Array<{ at: string; event_id: string; qualified: boolean; reason: string | null }> = row
    ? JSON.parse(row.category_history_json)
    : [];

  if (qualified) {
    currentCount = currentCount + 1;
    if (!isExcluded && currentCount >= AUTONOMY_THRESHOLD) {
      eligible = true;
    }
  } else {
    currentCount = 0;
    eligible = false;
  }

  history.push({ at: ts, event_id, qualified, reason: disqualified_reason });

  if (row) {
    db.prepare(
      `UPDATE consecutive_approvals
         SET current_count = ?, last_qualifying_at = ?, eligible_for_autonomy = ?,
             category_history_json = ?, updated_at = ?
       WHERE category = ?`,
    ).run(
      currentCount,
      qualified ? ts : null,
      eligible ? 1 : 0,
      JSON.stringify(history),
      ts,
      input.category,
    );
  } else {
    db.prepare(
      `INSERT INTO consecutive_approvals
         (category, current_count, last_qualifying_at, eligible_for_autonomy, category_history_json, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ).run(
      input.category,
      currentCount,
      qualified ? ts : null,
      eligible ? 1 : 0,
      JSON.stringify(history),
      ts,
    );
  }

  return { qualified, disqualified_reason, new_count: currentCount, eligible_for_autonomy: eligible, event_id };
}

export interface CounterSnapshot {
  category: string;
  current_count: number;
  last_qualifying_at: string | null;
  eligible_for_autonomy: boolean;
  category_history: Array<{ at: string; event_id: string; qualified: boolean; reason: string | null }>;
}

export function getCounter(db: DB, category: string): CounterSnapshot {
  const row = db
    .prepare(`SELECT * FROM consecutive_approvals WHERE category = ?`)
    .get(category) as
    | { category: string; current_count: number; last_qualifying_at: string | null; eligible_for_autonomy: number; category_history_json: string }
    | undefined;
  if (!row) {
    return { category, current_count: 0, last_qualifying_at: null, eligible_for_autonomy: false, category_history: [] };
  }
  return {
    category: row.category,
    current_count: row.current_count,
    last_qualifying_at: row.last_qualifying_at,
    eligible_for_autonomy: Boolean(row.eligible_for_autonomy),
    category_history: JSON.parse(row.category_history_json),
  };
}

export function enableAutonomy(db: DB, category: string, actor: string, reason: string): void {
  const ts = nowIso();
  db.prepare(
    `INSERT INTO autonomy_events (event_id, category, action, actor, reason, created_at) VALUES (?, ?, 'enable', ?, ?, ?)`,
  ).run(cryptoRandomId(), category, actor, reason, ts);
  db.prepare(
    `UPDATE consecutive_approvals SET eligible_for_autonomy = 1, updated_at = ? WHERE category = ?`,
  ).run(ts, category);
}

export function disableAutonomy(db: DB, category: string, actor: string, reason: string): void {
  const ts = nowIso();
  db.prepare(
    `INSERT INTO autonomy_events (event_id, category, action, actor, reason, created_at) VALUES (?, ?, 'disable', ?, ?, ?)`,
  ).run(cryptoRandomId(), category, actor, reason, ts);
  db.prepare(
    `UPDATE consecutive_approvals SET eligible_for_autonomy = 0, updated_at = ? WHERE category = ?`,
  ).run(ts, category);
}
