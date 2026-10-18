"""Run the service: python -m task1_knowledge_brain.service"""
from __future__ import annotations

import logging

import uvicorn

from .api import create_app
from .config import ServiceConfig


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = ServiceConfig()
    app = create_app(config=cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
