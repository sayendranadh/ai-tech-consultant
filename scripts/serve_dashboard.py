#!/usr/bin/env python3
"""Serve docs/dashboard.html with tokens auto-injected from .envs/.

The dashboard HTML on disk has placeholder="paste token". This server reads
the .envs/* files, substitutes the actual token values into the HTML at serve
time, and returns the result.

Tokens are NEVER written to disk. They live only in the served response.

This is a demo convenience. The served HTML has tokens in <input value="...">.
Acceptable on localhost. NOT acceptable if the page is ever exposed.

Usage:
    python3 scripts/serve_dashboard.py [--port 9000]
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENVS_DIR = ROOT / ".envs"
DOCS_DIR = ROOT / "docs"
DASHBOARD = DOCS_DIR / "dashboard.html"

ENV_FILES = {
    "KB_API_TOKEN_TASK2": ENVS_DIR / ".env.knowledge_brain",
    "T3_API_TOKEN": ENVS_DIR / ".env.meeting_to_scope",
}


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def _build_html() -> str:
    if not DASHBOARD.exists():
        return "<h1>docs/dashboard.html not found</h1>"
    html = DASHBOARD.read_text(encoding="utf-8")
    tokens = {k: _read_env_value(p, k) for k, p in ENV_FILES.items()}

    # Replace the placeholder on the Task 1 and Task 3 token inputs.
    # The dashboard HTML uses:
    #   <input id="t1-token" ... placeholder="paste token" />
    #   <input id="t3-token" ... placeholder="paste token" />
    # We inject value="..." for each.
    if tokens["KB_API_TOKEN_TASK2"]:
        html = html.replace(
            'id="t1-token" type="password" autocomplete="off" placeholder="paste token"',
            f'id="t1-token" type="password" autocomplete="off" value="{tokens["KB_API_TOKEN_TASK2"]}"',
            1,
        )
    if tokens["T3_API_TOKEN"]:
        html = html.replace(
            'id="t3-token" type="password" autocomplete="off" placeholder="paste token"',
            f'id="t3-token" type="password" autocomplete="off" value="{tokens["T3_API_TOKEN"]}"',
            1,
        )

    # Prefill the Task 3 project id.
    html = html.replace(
        'id="t3-project" type="text" placeholder="e.g. project_website"',
        'id="t3-project" type="text" placeholder="e.g. project_website" value="project_website"',
        1,
    )

    return html


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/dashboard.html", "/dashboard"):
            body = _build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            body = b"404 Not Found"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        # Suppress per-request access log noise; print only at startup.
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the dashboard with tokens injected.")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not DASHBOARD.exists():
        print(f"ERROR: {DASHBOARD} not found", file=sys.stderr)
        return 1

    Handler = DashboardHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer((args.host, args.port), Handler) as httpd:
            print(f"Serving dashboard with tokens injected at http://{args.host}:{args.port}/dashboard.html")
            print("Press Ctrl+C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
        return 0
    except OSError as exc:
        print(f"ERROR: could not bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
