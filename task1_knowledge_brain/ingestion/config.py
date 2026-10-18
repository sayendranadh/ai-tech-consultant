"""Configuration for Task 1 ingestion. Env-var driven; no secrets hard-coded."""
from __future__ import annotations

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    source_domain: str = Field(default="support.brilliantdirectories.com", alias="KB_SOURCE_DOMAIN")
    sitemap_url: str = Field(default="https://support.brilliantdirectories.com/support/sitemap.xml", alias="KB_SITEMAP_URL")
    user_agent: str = Field(default="BusinessLabsTechConsultant/0.1", alias="KB_USER_AGENT")
    max_pages_per_run: int = Field(default=500, alias="KB_MAX_PAGES_PER_RUN")
    pilot_limit: int = Field(default=3, alias="KB_PILOT_LIMIT")

    concurrency: int = Field(default=4, alias="KB_CONCURRENCY")
    requests_per_second: float = Field(default=2.0, alias="KB_REQUESTS_PER_SECOND")
    request_timeout_seconds: float = Field(default=30.0, alias="KB_REQUEST_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="KB_MAX_RETRIES")
    backoff_base_seconds: float = Field(default=1.0, alias="KB_BACKOFF_BASE_SECONDS")
    backoff_max_seconds: float = Field(default=30.0, alias="KB_BACKOFF_MAX_SECONDS")

    db_path: Path = Field(default=Path("./data/knowledge_brain.sqlite3"), alias="KB_DB_PATH")
    extraction_version: int = Field(default=1, alias="KB_EXTRACTION_VERSION")

    @field_validator("concurrency")
    @classmethod
    def _concurrency_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("KB_CONCURRENCY must be >= 1")
        return v

    @field_validator("requests_per_second")
    @classmethod
    def _rps_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("KB_REQUESTS_PER_SECOND must be > 0")
        return v
