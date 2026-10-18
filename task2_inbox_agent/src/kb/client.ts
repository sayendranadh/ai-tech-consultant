import createClient, { type Client } from "openapi-fetch";
import type { paths } from "./openapi.js";
import { ErrorEnvelopeSchema, QAResponseSchema, type KBAnswer } from "./schemas.js";

export class KBUnavailableError extends Error {
  override readonly cause?: unknown;
  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "KBUnavailableError";
    this.cause = cause;
  }
}

export class KBMalformedResponseError extends Error {
  readonly body?: unknown;
  constructor(message: string, body?: unknown) {
    super(message);
    this.name = "KBMalformedResponseError";
    this.body = body;
  }
}

export interface KBClientOptions {
  baseUrl: string;
  bearerToken: string;
  timeoutMs: number;
  maxRetries: number;
  backoffBaseMs: number;
  fetchImpl?: typeof fetch;
}

export interface KBQueryInput {
  question: string;
}

export class KBClient {
  private readonly http: Client<paths>;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly backoffBaseMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: KBClientOptions) {
    this.timeoutMs = opts.timeoutMs;
    this.maxRetries = opts.maxRetries;
    this.backoffBaseMs = opts.backoffBaseMs;
    this.fetchImpl = opts.fetchImpl ?? fetch;

    const wrappedFetch: typeof fetch = async (input, init) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        const merged: RequestInit = { ...(init ?? {}), signal: controller.signal };
        return await this.fetchImpl(input, merged);
      } finally {
        clearTimeout(timer);
      }
    };

    this.http = createClient<paths>({
      baseUrl: opts.baseUrl,
      headers: { Authorization: `Bearer ${opts.bearerToken}` },
      fetch: wrappedFetch,
    });
  }

  async query(input: KBQueryInput): Promise<KBAnswer> {
    let attempt = 0;
    let lastError: unknown = undefined;
    while (attempt <= this.maxRetries) {
      if (attempt > 0) {
        const wait = this.backoffBaseMs * Math.pow(2, attempt - 1);
        await sleep(wait);
      }
      try {
        const { data, error, response } = await this.http.POST("/query", {
          body: { question: input.question },
        });
        if (!response.ok) {
          if (response.status >= 500 || response.status === 429) {
            lastError = new KBUnavailableError(`kb returned ${response.status}`, error);
            attempt += 1;
            continue;
          }
          const envelope = ErrorEnvelopeSchema.safeParse(error);
          if (envelope.success) {
            throw new KBUnavailableError(
              `kb rejected query (${envelope.data.error.code}): ${envelope.data.error.message}`,
              envelope.data,
            );
          }
          throw new KBUnavailableError(`kb rejected query with status ${response.status}`, error);
        }
        const parsed = QAResponseSchema.safeParse(data);
        if (!parsed.success) {
          throw new KBMalformedResponseError("kb response failed schema validation", data);
        }
        return parsed.data;
      } catch (err) {
        if (err instanceof KBMalformedResponseError) throw err;
        if (err instanceof KBUnavailableError && err.message.startsWith("kb rejected query")) throw err;
        lastError = err;
        attempt += 1;
      }
    }
    if (lastError instanceof Error) {
      throw new KBUnavailableError(`kb unavailable after ${this.maxRetries + 1} attempts: ${lastError.message}`, lastError);
    }
    throw new KBUnavailableError(`kb unavailable after ${this.maxRetries + 1} attempts`);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
