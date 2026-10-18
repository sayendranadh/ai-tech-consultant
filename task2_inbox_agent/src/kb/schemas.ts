import { z } from "zod";

export const SourceRefSchema = z.object({
  title: z.string().nullable(),
  url: z.string(),
  section: z.string().nullable(),
  chunk_id: z.number().int(),
});

export const ImageRefSchema = z.object({
  src: z.string(),
  description: z.string().nullable(),
  model_id: z.string().nullable(),
  status: z.enum(["ok", "ambiguous", "failed", "simulated"]),
});

export const QAResponseSchema = z.object({
  question: z.string(),
  status: z.enum(["answered", "insufficient_evidence", "failed"]),
  answer: z.string(),
  sources: z.array(SourceRefSchema),
  image_refs: z.array(ImageRefSchema),
  escalation_required: z.boolean(),
});

export const ErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.number().int(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
});

export type KBAnswer = z.infer<typeof QAResponseSchema>;
export type KBSource = z.infer<typeof SourceRefSchema>;
