import { describe, it, expect } from "vitest";
import { KBClient, KBUnavailableError, KBMalformedResponseError } from "../src/kb/client.js";

type FetchInput = Parameters<typeof fetch>[0];
type FetchInit = Parameters<typeof fetch>[1];

function fakeFetchOnce(handler: (url: string, init?: FetchInit) => Response | Promise<Response>): typeof fetch {
  return (async (input: FetchInput, init?: FetchInit) => handler(String(input), init)) as typeof fetch;
}

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

const BASE = { baseUrl: "http://kb", bearerToken: "tok", timeoutMs: 1000, maxRetries: 2, backoffBaseMs: 1 } as const;

describe("KBClient", () => {
  it("returns validated QAResponse", async () => {
    const fetchImpl = fakeFetchOnce(async () => okResponse({ question: "q", status: "answered", answer: "a", sources: [], image_refs: [], escalation_required: false }));
    const c = new KBClient({ ...BASE, fetchImpl });
    const r = await c.query({ question: "q" });
    expect(r.status).toBe("answered");
  });

  it("throws KBMalformedResponseError on invalid body", async () => {
    const fetchImpl = fakeFetchOnce(async () => okResponse({ wrong: "shape" }));
    const c = new KBClient({ ...BASE, fetchImpl });
    await expect(c.query({ question: "q" })).rejects.toBeInstanceOf(KBMalformedResponseError);
  });

  it("retries on 503 then succeeds", async () => {
    let n = 0;
    const fetchImpl = fakeFetchOnce(async () => {
      n += 1;
      if (n < 3) return new Response("busy", { status: 503 });
      return okResponse({ question: "q", status: "answered", answer: "a", sources: [], image_refs: [], escalation_required: false });
    });
    const c = new KBClient({ ...BASE, fetchImpl });
    const r = await c.query({ question: "q" });
    expect(r.status).toBe("answered");
    expect(n).toBe(3);
  });

  it("throws KBUnavailableError after exhausting retries", async () => {
    const fetchImpl = fakeFetchOnce(async () => new Response("busy", { status: 503 }));
    const c = new KBClient({ ...BASE, fetchImpl });
    await expect(c.query({ question: "q" })).rejects.toBeInstanceOf(KBUnavailableError);
  });

  it("does not retry on 400 (client error)", async () => {
    let n = 0;
    const fetchImpl = fakeFetchOnce(async () => {
      n += 1;
      return new Response(JSON.stringify({ error: { code: 400, message: "bad" } }), { status: 400, headers: { "Content-Type": "application/json" } });
    });
    const c = new KBClient({ ...BASE, fetchImpl });
    await expect(c.query({ question: "q" })).rejects.toBeInstanceOf(KBUnavailableError);
    expect(n).toBe(1);
  });
});
