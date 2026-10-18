import { createHash } from "node:crypto";

const SIGNATURE_SEPARATORS = [/\n-- \n/, /\n—\n/];

export interface NormalizationConfig {
  signatureSeparators: RegExp[];
}

export const DEFAULT_NORMALIZATION: NormalizationConfig = {
  signatureSeparators: SIGNATURE_SEPARATORS,
};

export function normalize(text: string, cfg: NormalizationConfig = DEFAULT_NORMALIZATION): string {
  let t = text;
  for (const sep of cfg.signatureSeparators) {
    const idx = t.search(sep);
    if (idx >= 0) {
      t = t.slice(0, idx);
      break;
    }
  }
  t = t.trim();
  t = t.replace(/\s+/g, " ");
  t = t.toLowerCase();
  return t;
}

export function draftsEqual(generated: string, final: string, cfg?: NormalizationConfig): boolean {
  return normalize(generated, cfg) === normalize(final, cfg);
}

export function hashText(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}
