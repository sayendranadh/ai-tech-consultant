"""Task 3 configuration. Env-var driven; no secrets in source."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Task3Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_path: Path = Field(default=Path("./data/task3.sqlite3"), alias="T3_DB_PATH")
    chunk_max_chars: int = Field(default=1800, alias="T3_CHUNK_MAX_CHARS")
    chunk_overlap_chars: int = Field(default=200, alias="T3_CHUNK_OVERLAP_CHARS")
    api_token: str = Field(default="", alias="T3_API_TOKEN")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    claude_extractor_model: str = Field(default="", alias="CLAUDE_EXTRACTOR_MODEL")
    claude_prompt_version: str = Field(default="v1", alias="CLAUDE_PROMPT_VERSION")
