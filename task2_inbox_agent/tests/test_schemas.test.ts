import { describe, it, expect } from "vitest";
import { QAResponseSchema } from "../src/kb/schemas.js";

describe("kb schemas", () => {
  it("accepts a well-formed QAResponse", () => {
    const parsed = QAResponseSchema.parse({
      question: "q",
      status: "answered",
      answer: "a",
      sources: [{ title: "t", url: "u", section: "s", chunk_id: 1 }],
      image_refs: [],
      escalation_required: false,
    });
    expect(parsed.sources).toHaveLength(1);
  });
  it("rejects an unknown status", () => {
    expect(() => QAResponseSchema.parse({ status: "maybe", question: "", answer: "", sources: [], image_refs: [], escalation_required: false })).toThrow();
  });
});
