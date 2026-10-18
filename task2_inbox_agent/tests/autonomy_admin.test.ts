import { describe, it, expect } from "vitest";
import { openDb } from "../src/persistence/db.js";
import { enableAutonomy, disableAutonomy, getCounter, AUTONOMY_THRESHOLD } from "../src/autonomy/state_machine.js";

describe("autonomy admin", () => {
  it("enable/disable records audit events", () => {
    const db = openDb(":memory:");
    // Seed a counter so enable has something to update.
    db.prepare(
      `INSERT INTO consecutive_approvals (category, current_count, last_qualifying_at, eligible_for_autonomy, category_history_json, updated_at)
       VALUES ('how_to', 20, NULL, 0, '[]', 'now')`,
    ).run();
    enableAutonomy(db, "how_to", "admin@x", "20 consecutive approvals reached");
    expect(getCounter(db, "how_to").eligible_for_autonomy).toBe(true);
    const events = db.prepare(`SELECT * FROM autonomy_events WHERE category='how_to'`).all() as Array<{ action: string; actor: string }>;
    expect(events).toHaveLength(1);
    expect(events[0]!.action).toBe("enable");

    disableAutonomy(db, "how_to", "admin@x", "kill switch");
    expect(getCounter(db, "how_to").eligible_for_autonomy).toBe(false);
    const events2 = db.prepare(`SELECT * FROM autonomy_events WHERE category='how_to'`).all() as Array<{ action: string }>;
    expect(events2.map((e) => e.action)).toEqual(["enable", "disable"]);
  });

  it("threshold constant is 20", () => {
    expect(AUTONOMY_THRESHOLD).toBe(20);
  });
});
