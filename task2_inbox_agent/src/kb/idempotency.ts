import { createHash } from "node:crypto";

export function idempotencyKey(emailId: string, pipelineVersion: string): string {
  return createHash("sha256").update(`${emailId}::${pipelineVersion}`).digest("hex");
}
