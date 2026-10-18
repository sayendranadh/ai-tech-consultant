import { readFileSync } from "node:fs";
import { resolve } from "node:path";

interface Row {
  email_id: string;
  is_synthetic: boolean;
  expected: { category: string; escalation_required: boolean; risk: string };
}

const path = process.argv[2] ?? resolve(process.cwd(), "data/emails_v1.jsonl");
const lines = readFileSync(path, "utf8").split("\n").filter((l) => l.trim().length > 0);
const rows = lines.map((l) => JSON.parse(l) as Row);

const byCategory: Record<string, number> = {};
const byRisk: Record<string, number> = {};
let escalation = 0;
let notSynthetic = 0;

for (const r of rows) {
  byCategory[r.expected.category] = (byCategory[r.expected.category] ?? 0) + 1;
  byRisk[r.expected.risk] = (byRisk[r.expected.risk] ?? 0) + 1;
  if (r.expected.escalation_required) escalation += 1;
  if (!r.is_synthetic) notSynthetic += 1;
}

console.log(JSON.stringify({
  path,
  total: rows.length,
  by_category: byCategory,
  by_risk: byRisk,
  escalation_required: escalation,
  non_synthetic_flagged: notSynthetic,
}, null, 2));
