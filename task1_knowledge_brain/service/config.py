"""Service configuration. Secrets read from env; no defaults for tokens."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token_task2: str = Field(default="", alias="KB_API_TOKEN_TASK2")
    token_task3: str = Field(default="", alias="KB_API_TOKEN_TASK3")
    token_admin: str = Field(default="", alias="KB_API_TOKEN_ADMIN")

    rate_limit_per_minute: int = Field(default=10, alias="KB_RATE_LIMIT_PER_MINUTE")
    query_timeout_seconds: float = Field(default=30.0, alias="KB_QUERY_TIMEOUT_SECONDS")
    ingestion_request_timeout_seconds: float = Field(default=2.0, alias="KB_INGESTION_REQUEST_TIMEOUT_SECONDS")

    host: str = Field(default="127.0.0.1", alias="KB_SERVICE_HOST")
    port: int = Field(default=8000, alias="KB_SERVICE_PORT")
