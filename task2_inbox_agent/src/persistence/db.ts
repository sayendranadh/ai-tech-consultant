import Database from "better-sqlite3";

export type DB = Database.Database;

export function openDb(path: string): DB {
  const db = new Database(path);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  migrate(db);
  return db;
}

function migrate(db: DB): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS emails (
      email_id TEXT PRIMARY KEY,
      subject TEXT NOT NULL,
      body TEXT NOT NULL,
      thread_context TEXT,
      is_synthetic INTEGER NOT NULL DEFAULT 1,
      received_at TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS drafts (
      draft_id TEXT PRIMARY KEY,
      email_id TEXT NOT NULL,
      idempotency_key TEXT NOT NULL UNIQUE,
      category TEXT NOT NULL,
      urgency TEXT NOT NULL,
      risk TEXT NOT NULL,
      request_summary TEXT NOT NULL,
      draft_reply TEXT NOT NULL,
      supporting_sources_json TEXT NOT NULL,
      insufficient_evidence INTEGER NOT NULL,
      escalation_required INTEGER NOT NULL,
      human_approval_required INTEGER NOT NULL,
      recommended_next_action TEXT NOT NULL,
      model_id TEXT NOT NULL,
      prompt_version TEXT NOT NULL,
      draft_hash TEXT NOT NULL,
      generated_at TEXT NOT NULL,
      approval_status TEXT NOT NULL DEFAULT 'pending',
      FOREIGN KEY(email_id) REFERENCES emails(email_id)
    );
    CREATE INDEX IF NOT EXISTS idx_drafts_email ON drafts(email_id);
    CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(approval_status);

    CREATE TABLE IF NOT EXISTS approvals (
      approval_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      decision TEXT NOT NULL,
      final_reply TEXT,
      correction_reason TEXT,
      reviewer TEXT NOT NULL,
      approved_at TEXT NOT NULL,
      delivery_id TEXT,
      is_qualifying INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(draft_id) REFERENCES drafts(draft_id)
    );
    CREATE INDEX IF NOT EXISTS idx_approvals_draft ON approvals(draft_id);

    CREATE TABLE IF NOT EXISTS deliveries (
      delivery_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      mode TEXT NOT NULL,             -- 'simulated' for now
      delivered_text TEXT NOT NULL,
      is_simulated INTEGER NOT NULL DEFAULT 1,
      delivery_status TEXT NOT NULL,  -- 'delivered' | 'failed' | 'simulated_sent'
      error TEXT,
      created_at TEXT NOT NULL,
      FOREIGN KEY(draft_id) REFERENCES drafts(draft_id)
    );
    CREATE INDEX IF NOT EXISTS idx_deliveries_draft ON deliveries(draft_id);

    CREATE TABLE IF NOT EXISTS consecutive_approvals (
      category TEXT PRIMARY KEY,
      current_count INTEGER NOT NULL DEFAULT 0,
      last_qualifying_at TEXT,
      eligible_for_autonomy INTEGER NOT NULL DEFAULT 0,
      category_history_json TEXT NOT NULL DEFAULT '[]',
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS qualifying_events (
      event_id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      draft_id TEXT NOT NULL,
      delivery_id TEXT NOT NULL,
      generated_draft_hash TEXT NOT NULL,
      final_draft_hash TEXT NOT NULL,
      qualified INTEGER NOT NULL,
      disqualified_reason TEXT,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_qualifying_category ON qualifying_events(category);

    CREATE TABLE IF NOT EXISTS autonomy_events (
      event_id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      action TEXT NOT NULL,   -- 'enable' | 'disable'
      actor TEXT NOT NULL,
      reason TEXT,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_autonomy_category ON autonomy_events(category);

    CREATE INDEX IF NOT EXISTS idx_drafts_email_category ON drafts(category, email_id);
  `);
}
