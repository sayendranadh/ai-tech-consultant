"""Server-rendered HTML for the Knowledge Brain query UI.

This module returns HTML strings. It does not import FastAPI or auth.
The page is served without authentication (GET / is public so a reviewer can
reach the form); but the underlying /query endpoint still requires a bearer
token, which the user pastes into the form. The JS calls /query with that token.
"""
from __future__ import annotations


def render_query_page() -> str:
    return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Knowledge Brain — Query</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; line-height: 1.5; }
  label { display: block; margin-top: 1em; font-weight: 600; }
  input, textarea, button { font-family: inherit; font-size: 1rem; padding: 0.5em; width: 100%; box-sizing: border-box; }
  button { background: #0a66c2; color: #fff; border: none; padding: 0.75em; margin-top: 1em; cursor: pointer; border-radius: 4px; }
  button:disabled { background: #999; cursor: not-allowed; }
  .answer-box { border-left: 4px solid #0a66c2; padding: 1em; margin-top: 1.5em; background: #f7f9fc; white-space: pre-wrap; }
  .sources-box { margin-top: 1em; }
  .sources-box ul { padding-left: 1.2em; }
  .error-box { border-left: 4px solid #c00; background: #fee; padding: 1em; margin-top: 1em; }
  .status-line { margin-top: 1em; font-size: 0.9rem; color: #555; }
  .insufficient { border-left-color: #d97706; background: #fff8e1; }
</style>
</head>
<body>

<h1>Knowledge Brain — Query</h1>
<p><em>Ask a product question. Answers are grounded in the crawled knowledge base with citations. If the KB has no supporting evidence, the answer abstains.</em></p>

<label for="token">Bearer token (your <code>KB_API_TOKEN_TASK2</code>):</label>
<input id="token" type="password" autocomplete="off" placeholder="paste token" />

<label for="question">Question:</label>
<textarea id="question" rows="4" placeholder="e.g. How do I import members via CSV?"></textarea>

<button id="submit">Ask</button>

<div id="status" class="status-line"></div>
<div id="answer-wrap"></div>

<script>
(function () {
  var button = document.getElementById("submit");
  var statusEl = document.getElementById("status");
  var answerWrap = document.getElementById("answer-wrap");

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderAnswer(data) {
    answerWrap.innerHTML = "";
    var status = data.status || "unknown";

    var boxClass = "answer-box";
    if (status === "insufficient_evidence") boxClass += " insufficient";
    else if (status === "failed") boxClass = "error-box";

    var answerDiv = document.createElement("div");
    answerDiv.className = boxClass;
    answerDiv.textContent = data.answer || "(no answer text)";
    answerWrap.appendChild(answerDiv);

    if (data.sources && data.sources.length) {
      var sourcesDiv = document.createElement("div");
      sourcesDiv.className = "sources-box";
      var list = "<strong>Sources:</strong><ul>";
      for (var i = 0; i < data.sources.length; i++) {
        var s = data.sources[i];
        var label = s.title ? s.title + " — " : "";
        var section = s.section ? " (" + escapeHtml(s.section) + ")" : "";
        list += "<li>chunk_id=" + escapeHtml(String(s.chunk_id)) + " — "
              + "<a href='" + escapeHtml(s.url) + "' target='_blank' rel='noopener'>"
              + escapeHtml(s.url) + "</a>" + section + "</li>";
      }
      list += "</ul>";
      sourcesDiv.innerHTML = list;
      answerWrap.appendChild(sourcesDiv);
    }

    var metaDiv = document.createElement("div");
    metaDiv.className = "status-line";
    var bits = ["status: " + status];
    if (data.escalation_required) bits.push("escalation_required: true");
    metaDiv.textContent = bits.join(" | ");
    answerWrap.appendChild(metaDiv);
  }

  button.addEventListener("click", function () {
    var token = document.getElementById("token").value.trim();
    var question = document.getElementById("question").value.trim();
    answerWrap.innerHTML = "";

    if (!token) { setStatus("Enter your bearer token."); return; }
    if (!question) { setStatus("Enter a question."); return; }

    button.disabled = true;
    setStatus("Calling /query\u2026");
    var start = performance.now();

    fetch("/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify({ question: question }),
    }).then(function (resp) {
      return resp.json().then(function (body) {
        return { status: resp.status, body: body };
      });
    }).then(function (r) {
      var elapsed = Math.round(performance.now() - start);
      if (r.status !== 200) {
        var err = (r.body && (r.body.error && r.body.error.message || r.body.detail)) || "HTTP " + r.status;
        answerWrap.innerHTML = "<div class='error-box'><strong>Error (" + r.status + "):</strong> " + escapeHtml(String(err)) + "</div>";
        setStatus("Request failed after " + elapsed + " ms.");
      } else {
        renderAnswer(r.body);
        setStatus("Response received in " + elapsed + " ms.");
      }
      button.disabled = false;
    }).catch(function (err) {
      answerWrap.innerHTML = "<div class='error-box'><strong>Network error:</strong> " + escapeHtml(String(err)) + "</div>";
      setStatus("Network error.");
      button.disabled = false;
    });
  });
})();
</script>
</body>
</html>
"""
