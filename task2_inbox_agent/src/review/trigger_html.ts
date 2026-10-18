/**
 * Trigger form — lets a reviewer submit a synthetic email through the pipeline
 * without needing curl. 
 *
 * Flow:
 * 1. POST /emails   — insert the email into the DB
 * 2. POST /pipeline/process — run the pipeline
 * 3. Redirect to /review/{draft_id} on success
 * 4. On error, show an inline red banner (no raw JSON)
 *
 * All HTML/JS is plain — no framework, no build step.
 */
export function renderTriggerForm(): string {
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>Trigger pipeline — Task 2</title></head>
<body>
  <h1>Process a new email</h1>
  <p><a href="/review">&larr; back to pending drafts</a></p>
  <p><em>This form submits a synthetic email to the pipeline. If the live env
  vars are set (ANTHROPIC_API_KEY, CLAUDE_CLASSIFIER_MODEL, CLAUDE_DRAFTER_MODEL,
  KB_BEARER_TOKEN), the pipeline runs live. Otherwise it runs in mock mode.
  Either way, the draft is saved for review at /review.</em></p>

  <div id="status-banner" style="display:none;padding:8px;margin-bottom:12px"></div>

  <form id="trigger-form">
    <label>Email ID (stable identifier):<br/>
      <input name="email_id" type="text" required style="width:400px" />
    </label><br/><br/>

    <label>Subject:<br/>
      <input name="subject" type="text" required style="width:400px" />
    </label><br/><br/>

    <label>Body:<br/>
      <textarea name="body" rows="8" cols="80" required></textarea>
    </label><br/><br/>

    <button type="submit" id="trigger-submit">Process email</button>
  </form>

<script>
(function () {
  var form = document.getElementById("trigger-form");
  var button = document.getElementById("trigger-submit");
  var banner = document.getElementById("status-banner");

  function showBanner(kind, message) {
    banner.style.display = "block";
    banner.textContent = message;
    banner.style.background = kind === "error" ? "#fee" : "#efe";
    banner.style.border = "1px solid " + (kind === "error" ? "#c00" : "#0a0");
    banner.style.color = kind === "error" ? "#900" : "#050";
  }

  // Prefill the email_id with a timestamp-based unique value.
  form.elements["email_id"].value = "manual-" + Date.now();

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Processing\\u2026";
    banner.style.display = "none";

    var data = {
      email_id: form.elements["email_id"].value.trim(),
      subject: form.elements["subject"].value.trim(),
      body: form.elements["body"].value.trim(),
    };

    if (!data.email_id || !data.subject || !data.body) {
      showBanner("error", "All fields are required.");
      button.disabled = false;
      button.textContent = originalText;
      return;
    }

    // Step 1: insert the email into the DB.
    fetch("/emails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(function (insertResp) {
      if (!insertResp.ok) {
        return insertResp.json().catch(function () { return {}; }).then(function (j) {
          var msg = (j && j.message) || "insert failed";
          throw new Error("insert (status " + insertResp.status + "): " + msg);
        });
      }
      // Step 2: run the pipeline.
      return fetch("/pipeline/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: data.email_id }),
      }).then(function (pipelineResp) {
        if (!pipelineResp.ok) {
          return pipelineResp.json().catch(function () { return {}; }).then(function (j) {
            var msg = (j && j.message) || "pipeline failed";
            throw new Error("pipeline (status " + pipelineResp.status + "): " + msg);
          });
        }
        return pipelineResp.json();
      });
    }).then(function (result) {
      showBanner("ok", "Draft " + result.draft_id + " created. Redirecting\\u2026");
      setTimeout(function () { window.location.href = "/review/" + result.draft_id; }, 800);
    }).catch(function (err) {
      showBanner("error", err.message || String(err));
      button.disabled = false;
      button.textContent = originalText;
    });
  });
})();
</script>
</body></html>`;
}
