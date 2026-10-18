import type { DraftBody } from "./draft.js";

export interface SafeguardFinding {
  kind: "refund" | "price" | "delivery_date" | "feature_promise";
  matched: string;
  context: string;
}

const PATTERNS: Array<{ kind: SafeguardFinding["kind"]; re: RegExp }> = [
  { kind: "refund", re: /\b(refund|reimburs|money back)\b/i },
  { kind: "price", re: /\$\s?\d|\b(price|cost|fee)\b/i },
  {
    kind: "delivery_date",
    re: /\b(?:by|on|before|within)\s+(?:end of\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|this week|next week|the end of|day\s+\d+|hour\s+\d+)\b|\b(?:deliver|ship|arrive|go live)\b.*\b(?:by|on|before|within)\b/i,
  },
  { kind: "feature_promise", re: /\b(we will|we'll|guarantee)\b.*\b(add|build|release|ship|implement)\b/i },
];

export function detectUnauthorizedCommitments(
  draft: DraftBody,
  hasEvidence: boolean,
  isAuthorized: boolean,
): SafeguardFinding[] {
  if (hasEvidence && isAuthorized) return [];
  const findings: SafeguardFinding[] = [];
  const text = draft.draft_reply;
  for (const p of PATTERNS) {
    const m = p.re.exec(text);
    if (m) {
      findings.push({ kind: p.kind, matched: m[0], context: around(text, m.index) });
    }
  }
  return findings;
}

function around(text: string, at: number): string {
  const start = Math.max(0, at - 40);
  const end = Math.min(text.length, at + 80);
  return text.slice(start, end);
}
