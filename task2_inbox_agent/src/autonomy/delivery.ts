export interface DeliveryResult {
  delivery_id: string;
  mode: string;
  delivered_text: string;
  is_simulated: boolean;
  delivery_status: "delivered" | "failed" | "simulated_sent";
  error?: string;
}

export interface DeliveryAdapter {
  readonly mode: string;
  readonly is_simulated: boolean;
  deliver(input: { draft_id: string; to: string; text: string }): Promise<DeliveryResult>;
}

/**
 * SimulatedDeliveryAdapter: never emits external network calls.
 * Persisting the delivery is done by the caller (Dao). This adapter's only job
 * is to produce a DeliveryResult; the `delivery_status` is 'simulated_sent'
 * (NOT 'delivered') so a downstream reader cannot mistake it for a real send.
 */
export class SimulatedDeliveryAdapter implements DeliveryAdapter {
  readonly mode = "simulated";
  readonly is_simulated = true;

  async deliver(input: { draft_id: string; to: string; text: string }): Promise<DeliveryResult> {
    const delivery_id = cryptoRandomId();
    return {
      delivery_id,
      mode: this.mode,
      delivered_text: input.text,
      is_simulated: true,
      delivery_status: "simulated_sent",
    };
  }
}

/**
 * TestOnlyFailingAdapter: used by tests to prove that delivery failure does
 * NOT increment the 20-consecutive counter. Never constructed in the server.
 */
export class FailingDeliveryAdapter implements DeliveryAdapter {
  readonly mode = "simulated-fail";
  readonly is_simulated = true;

  async deliver(input: { draft_id: string; to: string; text: string }): Promise<DeliveryResult> {
    return {
      delivery_id: cryptoRandomId(),
      mode: this.mode,
      delivered_text: "",
      is_simulated: true,
      delivery_status: "failed",
      error: "simulated delivery failure (test-only adapter)",
    };
  }
}

function cryptoRandomId(): string {
  // crypto.randomUUID() available in Node 22
  return globalThis.crypto.randomUUID();
}
