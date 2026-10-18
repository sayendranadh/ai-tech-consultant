"""CLI:
  python -m task1_knowledge_brain.scheduler --limit 3
  python -m task1_knowledge_brain.scheduler --dry-run
"""
from __future__ import annotations

import argparse
import logging

from .daily_job import run_daily_ingestion_manual


def main() -> None:
    p = argparse.ArgumentParser(description="Task 1 daily ingestion (manual invocation)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_daily_ingestion_manual(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
