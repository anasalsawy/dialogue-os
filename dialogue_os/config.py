"""Configuration loaded from environment / .env. Never log secret values."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ROOT = Path("/home/azureuser/dialogue-os")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    dialogue_os_root: Path = Field(default=DEFAULT_ROOT, alias="DIALOGUE_OS_ROOT")

    telegram_owner_id: int | None = Field(default=None, alias="TELEGRAM_OWNER_ID")
    telegram_canonical_channel_id: int | None = Field(
        default=None, alias="TELEGRAM_CANONICAL_CHANNEL_ID"
    )

    telegram_chief_bot_token: str | None = Field(default=None, alias="TELEGRAM_CHIEF_BOT_TOKEN")
    telegram_builder_bot_token: str | None = Field(default=None, alias="TELEGRAM_BUILDER_BOT_TOKEN")
    telegram_research_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_RESEARCH_BOT_TOKEN"
    )
    telegram_operations_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_OPERATIONS_BOT_TOKEN"
    )
    telegram_growth_bot_token: str | None = Field(default=None, alias="TELEGRAM_GROWTH_BOT_TOKEN")
    telegram_customer_relations_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_CUSTOMER_RELATIONS_BOT_TOKEN"
    )
    telegram_stagehand_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_STAGEHAND_BOT_TOKEN"
    )
    telegram_watcher_alpha_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_WATCHER_ALPHA_BOT_TOKEN"
    )
    telegram_watcher_beta_bot_token: str | None = Field(
        default=None, alias="TELEGRAM_WATCHER_BETA_BOT_TOKEN"
    )

    cursor_cli_bin: str = Field(default="agent", alias="CURSOR_CLI_BIN")
    cursor_model: str | None = Field(default=None, alias="CURSOR_MODEL")
    cursor_timeout_seconds: int = Field(default=600, alias="CURSOR_TIMEOUT_SECONDS")
    cursor_control_session_key: str = Field(
        default="primary", alias="CURSOR_CONTROL_SESSION_KEY"
    )
    cursor_api_key: str | None = Field(default=None, alias="CURSOR_API_KEY")
    # None = auto-detect --force vs --yolo from `agent --help` (never both).
    cursor_force_flag: str | None = Field(default=None, alias="CURSOR_FORCE_FLAG")

    hermes_base_url: str | None = Field(default=None, alias="HERMES_BASE_URL")
    hermes_api_key: str | None = Field(default=None, alias="HERMES_API_KEY")
    hermes_model: str | None = Field(default=None, alias="HERMES_MODEL")
    hermes_max_output_tokens: int = Field(default=4096, alias="HERMES_MAX_OUTPUT_TOKENS")
    hermes_timeout_seconds: int = Field(default=120, alias="HERMES_TIMEOUT_SECONDS")

    browserbase_api_key: str | None = Field(default=None, alias="BROWSERBASE_API_KEY")
    browserbase_project_id: str | None = Field(default=None, alias="BROWSERBASE_PROJECT_ID")
    stagehand_enabled: bool = Field(default=False, alias="STAGEHAND_ENABLED")

    database_path: Path = Field(
        default=DEFAULT_ROOT / "data" / "dialogue_os.sqlite3", alias="DATABASE_PATH"
    )
    canonical_log_path: Path = Field(
        default=DEFAULT_ROOT / "data" / "canonical" / "events.jsonl",
        alias="CANONICAL_LOG_PATH",
    )
    # Active-mission supervision. The supervisor ticks on this interval and
    # inspects any mission whose persisted next_check_at has passed; 0 disables.
    supervision_tick_seconds: int = Field(default=15, alias="SUPERVISION_TICK_SECONDS")
    mission_ack_timeout_seconds: int = Field(default=300, alias="MISSION_ACK_TIMEOUT_SECONDS")
    mission_heartbeat_timeout_seconds: int = Field(
        default=600, alias="MISSION_HEARTBEAT_TIMEOUT_SECONDS"
    )
    mission_owner_update_seconds: int = Field(
        default=1800, alias="MISSION_OWNER_UPDATE_SECONDS"
    )
    mission_max_unsupported_claims: int = Field(
        default=2, alias="MISSION_MAX_UNSUPPORTED_CLAIMS"
    )
    mission_supervision_watcher: str = Field(
        default="watcher_alpha", alias="MISSION_SUPERVISION_WATCHER"
    )

    health_bind: str = Field(default="127.0.0.1", alias="HEALTH_BIND")
    health_port: int = Field(default=8787, alias="HEALTH_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_user: str = Field(default="azureuser", alias="SERVICE_USER")
    bot_to_bot_chatter: bool = Field(default=False, alias="BOT_TO_BOT_CHATTER")
    azure_llm_disabled: bool = Field(default=True, alias="AZURE_LLM_DISABLED")

    @field_validator("dialogue_os_root", "database_path", "canonical_log_path", mode="before")
    @classmethod
    def _path(cls, v: Any) -> Path:
        return Path(v).expanduser().resolve() if v else v

    @field_validator(
        "telegram_owner_id",
        "telegram_canonical_channel_id",
        mode="before",
    )
    @classmethod
    def _empty_int_none(cls, v: Any) -> Any:
        if v is None or v == "":
            return None
        return v

    @field_validator(
        "telegram_chief_bot_token",
        "telegram_builder_bot_token",
        "telegram_research_bot_token",
        "telegram_operations_bot_token",
        "telegram_growth_bot_token",
        "telegram_customer_relations_bot_token",
        "telegram_stagehand_bot_token",
        "telegram_watcher_alpha_bot_token",
        "telegram_watcher_beta_bot_token",
        "hermes_base_url",
        "hermes_api_key",
        "hermes_model",
        "browserbase_api_key",
        "browserbase_project_id",
        "cursor_model",
        "cursor_api_key",
        "cursor_force_flag",
        mode="before",
    )
    @classmethod
    def _empty_str_none(cls, v: Any) -> Any:
        if v is None or v == "":
            return None
        return v

    @field_validator("cursor_force_flag", mode="before")
    @classmethod
    def _force_flag(cls, v: Any) -> str | None:
        if v is None or v == "":
            return None
        val = str(v).strip().lower()
        if val in ("force", "--force"):
            return "--force"
        if val in ("yolo", "--yolo"):
            return "--yolo"
        raise ValueError("CURSOR_FORCE_FLAG must be '--force', '--yolo', or empty (auto-detect)")

    def bot_token_map(self) -> dict[str, str]:
        mapping = {
            "chief": self.telegram_chief_bot_token,
            "builder": self.telegram_builder_bot_token,
            "researcher": self.telegram_research_bot_token,
            "operations": self.telegram_operations_bot_token,
            "growth": self.telegram_growth_bot_token,
            "customer_relations": self.telegram_customer_relations_bot_token,
            "stagehand": self.telegram_stagehand_bot_token,
            "watcher_alpha": self.telegram_watcher_alpha_bot_token,
            "watcher_beta": self.telegram_watcher_beta_bot_token,
        }
        return {k: v for k, v in mapping.items() if v and v.strip()}

    def missing_required_for_bridge(self) -> list[str]:
        missing: list[str] = []
        if not self.telegram_chief_bot_token:
            missing.append("TELEGRAM_CHIEF_BOT_TOKEN")
        if self.telegram_owner_id is None:
            missing.append("TELEGRAM_OWNER_ID")
        return missing

    def missing_for_hermes(self) -> list[str]:
        missing: list[str] = []
        if not self.hermes_base_url:
            missing.append("HERMES_BASE_URL")
        if not self.hermes_api_key:
            missing.append("HERMES_API_KEY")
        if not self.hermes_model:
            missing.append("HERMES_MODEL")
        return missing

    def assert_no_azure_llm(self) -> None:
        if not self.azure_llm_disabled:
            raise RuntimeError("AZURE_LLM_DISABLED must remain true; Azure LLM is not allowed.")
        for key in (
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "OPENAI_API_BASE",
            "AZURE_AI_PROJECT_ENDPOINT",
        ):
            val = os.environ.get(key)
            if val and "azure" in val.lower():
                raise RuntimeError(f"Refusing Azure LLM dependency via {key}")


@lru_cache
def get_settings() -> Settings:
    root = os.environ.get("DIALOGUE_OS_ROOT", str(DEFAULT_ROOT))
    env_file = Path(root) / ".env"
    if env_file.exists():
        return Settings(_env_file=str(env_file))
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
