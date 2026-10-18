import type { DraftRow } from "../persistence/dao.js";

function esc(s: string | null | undefined): string {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderPendingList(rows: DraftRow[]): string {
  const items = rows
    .map(
      (r) => `<li>
        <a href="/review/${esc(r.draft_id)}">${esc(r.email_id)} — ${esc(r.category)} — urgency ${esc(r.urgency)} — risk ${esc(r.risk)}</a>
      </li>`,
    )
    .join("\n");
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>Pending drafts — Task 2 Review</title></head>
<body>
  <h1>Pending drafts (${rows.length})</h1>
  <p><a href="/trigger" style="font-size:1.2em;font-weight:bold">+ Process new email</a></p>
  <p><em>Simulated delivery only. No real email is sent by this interface.</em></p>
  <ul>${items}</ul>

<script>
// Loading indicator: disable submit buttons on form submit.
// Errors after a failed POST currently surface as raw JSON from the API.
// That is a known limitation documented in REPORT.md (no JS-based error
// rendering in this milestone).
document.querySelectorAll("form").forEach(function (f) {
  f.addEventListener("submit", function () {
    f.querySelectorAll("button[type='submit']").forEach(function (b) {
      b.disabled = true;
      b.dataset.origText = b.textContent;
      b.textContent = "Submitting…";
    });
  });
});
</script>
</body></html>`;
}

export function renderDraftDetail(args: {
  draft: DraftRow;
  email: { subject: string; body: string } | undefined;
  sources: Array<{ url: string; section: string | null; chunk_id: number; title: string | null }>;
  approvals: Array<Record<string, unknown>>;
  counter: { current_count: number; eligible_for_autonomy: boolean } | null;
  exclusion_list: string[];
}): string {
  const { draft, email, sources, approvals, counter, exclusion_list } = args;
  const isExcluded = exclusion_list.includes(draft.category);
  const sourcesHtml = sources.length
    ? `<ul>${sources.map((s) => `<li>chunk_id=${s.chunk_id} — ${esc(s.url)}${s.section ? ` (${esc(s.section)})` : ""}</li>`).join("")}</ul>`
    : `<p><strong>No evidence retrieved.</strong></p>`;
  const warnings: string[] = [];
  if (draft.insufficient_evidence) warnings.push("INSUFFICIENT EVIDENCE — draft was generated without cited sources.");
  if (draft.escalation_required) warnings.push("ESCALATION RECOMMENDED — review carefully.");
  const warningsHtml = warnings.length ? `<div style="border:1px solid #c00;padding:8px;background:#fee"><strong>WARNINGS</strong><ul>${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : "";
  const approvalsHtml = approvals.length
    ? `<table border="1" cellpadding="4"><tr><th>decision</th><th>reviewer</th><th>at</th><th>correction_reason</th></tr>${approvals
        .map(
          (a) =>
            `<tr><td>${esc(String(a.decision))}</td><td>${esc(String(a.reviewer))}</td><td>${esc(String(a.approved_at))}</td><td>${esc(String(a.correction_reason ?? ""))}</td></tr>`,
        )
        .join("")}</table>`
    : "<p>No review history yet.</p>";
  const counterHtml = counter
    ? `<p>Category <strong>${esc(draft.category)}</strong>: consecutive unchanged approvals = <strong>${counter.current_count}</strong>; eligible_for_autonomy = <strong>${counter.eligible_for_autonomy}</strong>${isExcluded ? " <em>(category is in high-risk exclusion list; never eligible)</em>" : ""}</p>`
    : "";

  return `<!doctype html>
<html><head><meta charset="utf-8"><title>Draft ${esc(draft.draft_id)}</title></head>
<body>
  <h1>Draft ${esc(draft.draft_id)}</h1>
  <p><a href="/review">← back to list</a></p>
  ${warningsHtml}
  <h2>Original email (${esc(draft.email_id)})</h2>
  <p><strong>Subject:</strong> ${esc(email?.subject)}</p>
  <pre>${esc(email?.body)}</pre>
  <h2>Classification</h2>
  <ul>
    <li>category: ${esc(draft.category)}</li>
    <li>urgency: ${esc(draft.urgency)}</li>
    <li>risk: ${esc(draft.risk)}</li>
    <li>model_id: ${esc(draft.model_id)}</li>
    <li>prompt_version: ${esc(draft.prompt_version)}</li>
  </ul>
  ${counterHtml}
  <h2>Generated draft</h2>
  <pre>${esc(draft.draft_reply)}</pre>
  <h2>Supporting sources</h2>
  ${sourcesHtml}
  <h2>Review history</h2>
  ${approvalsHtml}
  <h2>Actions</h2>
  <p><em>All deliveries are SIMULATED. No real email is sent. Approved sends are recorded as simulated_sent.</em></p>
  <form method="POST" action="/review/${esc(draft.draft_id)}/action">
    <label>Delivery target email: <input name="delivery_target" type="email" required /></label><br/>
    <label>Correction reason (optional): <input name="correction_reason" type="text" /></label><br/>

    <fieldset>
      <legend>Approve &amp; send</legend>
      <button name="action" value="approve" type="submit">Approve and simulate send</button>
    </fieldset>

    <fieldset>
      <legend>Edit &amp; send</legend>
      <textarea name="edited_text" rows="8" cols="80">${esc(draft.draft_reply)}</textarea><br/>
      <button name="action" value="edit" type="submit">Save edit and simulate send</button>
    </fieldset>

    <fieldset>
      <legend>Reject and provide replacement</legend>
      <textarea name="replacement_text" rows="6" cols="80"></textarea><br/>
      <button name="action" value="reject" type="submit">Reject with replacement</button>
    </fieldset>

    <fieldset>
      <legend>Escalate to human expert</legend>
      <button name="action" value="escalate" type="submit">Escalate</button>
    </fieldset>
  </form>
</body></html>`;
}
