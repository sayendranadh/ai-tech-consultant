import Fastify, { type FastifyReply, type FastifyRequest } from "fastify";
import fastifyCors from "@fastify/cors";
import { registerRequestId } from "./middleware/request_id.js";
import { loadConfig } from "./config.js";
import { openDb } from "./persistence/db.js";
import { Dao, type DraftRow } from "./persistence/dao.js";
import { KBClient } from "./kb/client.js";
import { MockClassifier, ClaudeClassifier } from "./pipeline/classify.js";
import { MockDrafter, ClaudeDrafter } from "./pipeline/draft.js";
import { PipelineRunner } from "./pipeline/runner.js";
import { loadMockFixtures } from "./fixtures/loader.js";
import { SimulatedDeliveryAdapter } from "./autonomy/delivery.js";
import { ReviewService, HIGH_RISK_EXCLUSIONS_DEFAULT } from "./review/service.js";
import { renderPendingList, renderDraftDetail } from "./review/html.js";
import { renderTriggerForm } from "./review/trigger_html.js";
import {
  getCounter,
  enableAutonomy,
  disableAutonomy,
  AUTONOMY_THRESHOLD,
} from "./autonomy/state_machine.js";

async function main(): Promise<void> {
  const cfg = loadConfig();
  const db = openDb(cfg.T2_DB_PATH);
  const dao = new Dao(db);
  const adapter = new SimulatedDeliveryAdapter();
  const reviewService = new ReviewService(dao, adapter, db);
  const exclusionList = HIGH_RISK_EXCLUSIONS_DEFAULT;

  const kb = new KBClient({
    baseUrl: cfg.KB_BASE_URL,
    bearerToken: cfg.KB_BEARER_TOKEN,
    timeoutMs: cfg.KB_QUERY_TIMEOUT_MS,
    maxRetries: cfg.KB_MAX_RETRIES,
    backoffBaseMs: cfg.KB_BACKOFF_BASE_MS,
  });

  let classifier;
  let drafter;
  if (cfg.ANTHROPIC_API_KEY && cfg.CLAUDE_CLASSIFIER_MODEL && cfg.CLAUDE_DRAFTER_MODEL) {
    classifier = new ClaudeClassifier(cfg.ANTHROPIC_API_KEY, cfg.CLAUDE_CLASSIFIER_MODEL, cfg.CLAUDE_PROMPT_VERSION);
    drafter = new ClaudeDrafter(cfg.ANTHROPIC_API_KEY, cfg.CLAUDE_DRAFTER_MODEL, cfg.CLAUDE_PROMPT_VERSION);
  } else {
    const fixtures = loadMockFixtures();
    classifier = new MockClassifier(fixtures.classifications);
    drafter = new MockDrafter(fixtures.drafts);
  }

  const runner = new PipelineRunner({ dao, classifier, drafter, kb, pipelineVersion: cfg.CLAUDE_PROMPT_VERSION });

  const app = Fastify({ logger: true });
  await registerRequestId(app);

  await app.register(import("@fastify/formbody"));

  // Demo CORS: allows the static dashboard at docs/dashboard.html to call the API
  // from file:// (Origin: null). NOT acceptable for production.
  await app.register(fastifyCors, {
    origin: true,
    credentials: false,
    methods: ["GET", "POST", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
    strictPreflight: false,
  });

  // Belt-and-suspenders: ensure Access-Control-Allow-Origin is on every response.
  app.addHook("onSend", async (_req, reply, payload) => {
    reply.header("Access-Control-Allow-Origin", "*");
    return payload;
  });

  app.get("/health", async () => ({ status: "ok" }));

  app.post<{ Body: { email_id: string } }>("/pipeline/process", async (req, reply) => {
    const parsed = (req.body ?? {}) as { email_id?: string };
    if (!parsed.email_id) {
      return reply.code(400).send({ error: { code: 400, message: "email_id required" } });
    }
    const result = await runner.processEmail(parsed.email_id);
    return reply.code(200).send({
      draft_id: result.draft_id,
      email_id: result.body.email_id,
      predicted_category: result.body.predicted_category,
      urgency: result.body.urgency,
      risk: result.body.risk,
      human_approval_required: result.body.human_approval_required,
      insufficient_evidence: result.body.insufficient_evidence,
      escalation_required: result.body.escalation_required,
    });
  });

  app.post<{ Body: { email_id?: string; subject?: string; body?: string; thread_context?: string } }>("/emails", async (req, reply) => {
    const parsed = (req.body ?? {}) as { email_id?: string; subject?: string; body?: string; thread_context?: string };
    if (!parsed.email_id || !parsed.subject || !parsed.body) {
      return reply.code(400).send({ error: { code: 400, message: "email_id, subject, and body are required" } });
    }
    try {
      const insertArgs: Parameters<Dao["insertEmail"]>[0] = {
        email_id: parsed.email_id,
        subject: parsed.subject,
        body: parsed.body,
        received_at: new Date().toISOString(),
        is_synthetic: true,
      };
      if (parsed.thread_context !== undefined) {
        insertArgs.thread_context = parsed.thread_context;
      }
      dao.insertEmail(insertArgs);
      return reply.code(201).send({ inserted: true, email_id: parsed.email_id });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return reply.code(500).send({ error: { code: 500, message } });
    }
  });

  app.get("/", async (_req, reply) => {
    reply.type("text/html").send(renderTriggerForm());
  });

  app.get("/trigger", async (_req, reply) => {
    reply.type("text/html").send(renderTriggerForm());
  });

  app.get("/review", async (_req, reply) => {
    const rows = dao.listPendingDrafts();
    reply.type("text/html").send(renderPendingList(rows));
  });

  app.get<{ Params: { draft_id: string } }>("/review/:draft_id", async (req, reply) => {
    const draft = dao.getDraft(req.params.draft_id);
    if (!draft) return reply.code(404).type("text/html").send("<h1>Draft not found</h1>");
    const email = dao.getEmail(draft.email_id);
    const sources = JSON.parse(draft.supporting_sources_json) as Array<{ url: string; section: string | null; chunk_id: number; title: string | null }>;
    const approvals = dao.listApprovalsForDraft(req.params.draft_id);
    const counter = getCounter(db, draft.category);
    reply.type("text/html").send(
      renderDraftDetail({
        draft,
        email: email ? { subject: email.subject, body: email.body } : undefined,
        sources,
        approvals,
        counter,
        exclusion_list: exclusionList,
      }),
    );
  });

  app.post<{ Params: { draft_id: string }; Body: Record<string, string> }>(
    "/review/:draft_id/action",
    async (req, reply) => {
      const body = (req.body ?? {}) as Record<string, string>;
      const action = body.action;
      if (action !== "approve" && action !== "edit" && action !== "reject" && action !== "escalate") {
        return reply.code(400).send({ error: { code: 400, message: "invalid action" } });
      }
      try {
        const result = await reviewService.apply({
          draft_id: req.params.draft_id,
          action,
          edited_text: body.edited_text,
          replacement_text: body.replacement_text,
          correction_reason: body.correction_reason,
          reviewer: "reviewer@localhost",
          delivery_target: body.delivery_target || "unknown@simulated",
          exclusion_list: exclusionList,
        });
        return reply.redirect(`/review/${req.params.draft_id}`, 303);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return reply.code(400).send({ error: { code: 400, message } });
      }
    },
  );

  app.get("/admin/autonomy/:category", async (req: FastifyRequest<{ Params: { category: string } }>, reply: FastifyReply) => {
    const counter = getCounter(db, req.params.category);
    return reply.send({
      threshold: AUTONOMY_THRESHOLD,
      excluded_categories: exclusionList,
      counter,
    });
  });

  app.post<{ Params: { category: string }; Body: { actor: string; reason: string } }>(
    "/admin/autonomy/:category/enable",
    async (req, reply) => {
      const actor = (req.body as { actor?: string })?.actor;
      const reason = (req.body as { reason?: string })?.reason;
      if (!actor || !reason) return reply.code(400).send({ error: { code: 400, message: "actor and reason required" } });
      if (exclusionList.includes(req.params.category)) {
        return reply.code(400).send({ error: { code: 400, message: "category is in exclusion list" } });
      }
      enableAutonomy(db, req.params.category, actor, reason);
      return reply.send({ enabled: true, category: req.params.category });
    },
  );

  app.post<{ Params: { category: string }; Body: { actor: string; reason: string } }>(
    "/admin/autonomy/:category/disable",
    async (req, reply) => {
      const actor = (req.body as { actor?: string })?.actor;
      const reason = (req.body as { reason?: string })?.reason;
      if (!actor || !reason) return reply.code(400).send({ error: { code: 400, message: "actor and reason required" } });
      disableAutonomy(db, req.params.category, actor, reason);
      return reply.send({ enabled: false, category: req.params.category });
    },
  );

  const port = Number(process.env.T2_PORT ?? 8100);
  await app.listen({ host: "127.0.0.1", port });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
