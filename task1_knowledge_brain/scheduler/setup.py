"""APScheduler configuration with SQLAlchemyJobStore on the same SQLite file.

Called from FastAPI lifespan if KB_SCHEDULER_ENABLED=true.
"""
from __future__ import annotations

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..ingestion.config import IngestionConfig
from .daily_job import run_daily_ingestion

log = logging.getLogger(__name__)


def build_scheduler(cfg: IngestionConfig, cron_hour: int = 2, cron_minute: int = 0) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{cfg.db_path}")}
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    scheduler.add_job(
        run_daily_ingestion,
        trigger=CronTrigger(hour=cron_hour, minute=cron_minute),
        id="daily_ingestion",
        kwargs={"source": cfg.source_domain},
        replace_existing=True,
        max_instances=1,     # prevent overlapping runs
        coalesce=True,       # if a run was missed, run once
        misfire_grace_time=3600,
    )
    return scheduler
