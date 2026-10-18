import type { FastifyInstance } from "fastify";
import { randomUUID } from "node:crypto";

export async function registerRequestId(app: FastifyInstance): Promise<void> {
  app.addHook("onRequest", async (req, reply) => {
    const incoming = req.headers["x-request-id"];
    const rid = typeof incoming === "string" && incoming.length > 0 ? incoming : randomUUID();
    (req as unknown as { requestId: string }).requestId = rid;
    reply.header("x-request-id", rid);
  });

  app.addHook("onResponse", async (req, reply) => {
    const rid = (req as unknown as { requestId?: string }).requestId ?? "";
    req.log.info(
      JSON.stringify({
        event: "request",
        request_id: rid,
        method: req.method,
        path: req.url,
        status: reply.statusCode,
        elapsed_ms: Math.round(reply.elapsedTime),
      }),
    );
  });
}
