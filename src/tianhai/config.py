from __future__ import annotations

from enum import StrEnum

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class DatabaseBackend(StrEnum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class TianHaiSettings(BaseSettings):
    """Environment-driven runtime settings for TianHai."""

    model_config = SettingsConfigDict(
        env_prefix="TIANHAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_id: str = Field(default="tianhai", min_length=1)
    app_name: str = Field(default="TianHai", min_length=1)
    app_description: str = (
        "TianHai Java service log analysis assistant runtime foundation."
    )
    environment: str = Field(default="local", min_length=1)

    database_url: str | None = None
    sqlite_db_file: str = Field(default="data/tianhai-agentos.db", min_length=1)

    agentos_telemetry: bool = False
    agentos_reload: bool = False
    agentos_auto_provision_dbs: bool = True
    primary_agent_model: str = Field(default="openai:gpt-4o", min_length=1)
    java_log_team_model: str = Field(default="openai:gpt-4o", min_length=1)

    @field_validator("database_url", mode="before")
    @classmethod
    def blank_database_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def database_backend(self) -> DatabaseBackend:
        if self.database_url is None:
            return DatabaseBackend.SQLITE
        if self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            return DatabaseBackend.POSTGRES
        raise ValueError("TIANHAI_DATABASE_URL must be a PostgreSQL URL.")
