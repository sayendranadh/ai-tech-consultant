import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ClassificationSchema } from "../pipeline/classify.js";
import { DraftBodySchema } from "../pipeline/draft.js";

const FIXTURES_PATH = process.env.T2_FIXTURES_PATH ?? resolve(process.cwd(), "data/mock_fixtures.json");

export interface MockFixtures {
  classifications: Record<string, ReturnType<typeof ClassificationSchema.parse>>;
  drafts: Record<string, ReturnType<typeof DraftBodySchema.parse>>;
}

export function loadMockFixtures(): MockFixtures {
  const raw = JSON.parse(readFileSync(FIXTURES_PATH, "utf8")) as { classifications: Record<string, unknown>; drafts: Record<string, unknown> };
  const classifications: MockFixtures["classifications"] = {};
  for (const [k, v] of Object.entries(raw.classifications)) classifications[k] = ClassificationSchema.parse(v);
  const drafts: MockFixtures["drafts"] = {};
  for (const [k, v] of Object.entries(raw.drafts)) drafts[k] = DraftBodySchema.parse(v);
  return { classifications, drafts };
}
