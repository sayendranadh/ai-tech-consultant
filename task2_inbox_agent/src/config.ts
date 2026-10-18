import { z } from "zod";

const EnvSchema = z.object({
  T2_DB_PATH: z.string().min(1).default("./data/task2.sqlite3"),

  KB_BASE_URL: z.string().url().default("http://127.0.0.1:8000"),
  KB_BEARER_TOKEN: z.string().min(1),
  KB_QUERY_TIMEOUT_MS: z.coerce.number().int().positive().default(30000),
  KB_MAX_RETRIES: z.coerce.number().int().min(0).default(2),
  KB_BACKOFF_BASE_MS: z.coerce.number().int().nonnegative().default(500),

  ANTHROPIC_API_KEY: z.string().optional(),
  CLAUDE_CLASSIFIER_MODEL: z.string().optional(),
  CLAUDE_DRAFTER_MODEL: z.string().optional(),
  CLAUDE_PROMPT_VERSION: z.string().default("v1"),

  EMAIL_DELIVERY_ADAPTER: z.enum(["simulated"]).default("simulated"),
});

export type Config = z.infer<typeof EnvSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const parsed = EnvSchema.safeParse(env);
  if (!parsed.success) {
    const msg = parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
    throw new Error(`invalid Task 2 configuration: ${msg}`);
  }
  return parsed.data;
}
