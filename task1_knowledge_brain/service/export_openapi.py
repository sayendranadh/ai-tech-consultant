"""Export OpenAPI to docs/api/knowledge_brain.openapi.json for review and for Tasks 2/3."""
from __future__ import annotations

import json
from pathlib import Path

from .api import create_app
from .config import ServiceConfig


def main() -> None:
    app = create_app(config=ServiceConfig())
    spec = app.openapi()
    out = Path("docs/api/knowledge_brain.openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
