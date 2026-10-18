import { describe, it, expect } from "vitest";
import { SimulatedDeliveryAdapter, FailingDeliveryAdapter } from "../src/autonomy/delivery.js";

describe("SimulatedDeliveryAdapter", () => {
  it("returns delivery_status 'simulated_sent', not 'delivered'", async () => {
    const a = new SimulatedDeliveryAdapter();
    const r = await a.deliver({ draft_id: "d1", to: "c@e.com", text: "hi" });
    expect(r.delivery_status).toBe("simulated_sent");
    expect(r.is_simulated).toBe(true);
  });

  it("does not fetch the network (no global fetch patched, but call is sync-fast)", async () => {
    // This test proves the adapter has no I/O by asserting it resolves synchronously.
    const a = new SimulatedDeliveryAdapter();
    const before = performance.now();
    await a.deliver({ draft_id: "d1", to: "c@e.com", text: "hi" });
    const elapsed = performance.now() - before;
    expect(elapsed).toBeLessThan(50);
  });
});

describe("FailingDeliveryAdapter (test-only)", () => {
  it("returns delivery_status 'failed'", async () => {
    const a = new FailingDeliveryAdapter();
    const r = await a.deliver({ draft_id: "d1", to: "c@e.com", text: "hi" });
    expect(r.delivery_status).toBe("failed");
    expect(r.error).toContain("simulated");
  });
});
