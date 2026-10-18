import { describe, it, expect } from "vitest";
import { openDb } from "../src/persistence/db.js";
import { recordQualifyingEvent, getCounter } from "../src/autonomy/state_machine.js";

describe("duplicate qualifying event", () => {
  it("same (category, draft_id, delivery_id) qualified twice increments once", () => {
    const db = openDb(":memory:");
    const input = {
      category: "how_to",
      draft_id: "d-1",
      delivery_id: "del-1",
      generated_draft: "text",
      final_draft: "text",
      delivery_status: "simulated_sent" as const,
      exclusion_list: [] as string[],
    };
    const r1 = recordQualifyingEvent(db, input);
    expect(r1.qualified).toBe(true);
    expect(getCounter(db, "how_to").current_count).toBe(1);
    const r2 = recordQualifyingEvent(db, input);
    expect(r2.qualified).toBe(false);
    expect(r2.disqualified_reason).toBe("duplicate_event");
    expect(getCounter(db, "how_to").current_count).toBe(1);
  });
});
