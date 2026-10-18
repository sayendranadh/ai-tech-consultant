"""CLI: python -m task1_knowledge_brain.ingestion [--limit N] [--dry-run]"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from .config import IngestionConfig
from .orchestrator import run_ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 1 ingestion")
    parser.add_argument("--limit", type=int, default=None, help="Pilot mode: cap total URLs")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions without writing")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = IngestionConfig()
    report = asyncio.run(run_ingestion(cfg, limit=args.limit, dry_run=args.dry_run))
    print(json.dumps({"started_at": report.started_at, "finished_at": report.finished_at, "counts": report.counts, "errors": report.errors}, indent=2))


if __name__ == "__main__":
    main()
