from __future__ import annotations

from functools import lru_cache
from typing import Any, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Telegram ---
    BOT_TOKEN: str
    ADMIN_IDS: list[int] = []
    INDEX_CHANNEL_ID: int
    LOG_CHANNEL_ID: int       # Receives indexing logs, ban logs, deletion logs
    REQUEST_CHANNEL_ID: int | None = None   # Receives /request moderation cards & inline buttons

    # --- Force Sub ---
    FORCE_SUB_CHANNELS: Any = []
    FORCE_SUB_LINKS: Any = []

    # --- Postgres ---
    POSTGRES_USER: str = "bot_user"
    POSTGRES_PASSWORD: str = "change_me"
    POSTGRES_DB: str = "tv_series_bot"
    DATABASE_URL: str

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- App ---
    TMDB_API_KEY: str | None = None
    SQL_ECHO: bool = False
    LOG_LEVEL: str = "INFO"
    AUTO_DELETE_SECONDS: int = 120

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v]
        return v
        
    @field_validator("REQUEST_CHANNEL_ID", mode="before")
    @classmethod
    def parse_request_channel(cls, v: Any, info: Any) -> int:
        if v is None or str(v).strip() == "":
            return int(info.data.get("LOG_CHANNEL_ID"))
        return int(v)
        
    @field_validator(
        "FORCE_SUB_CHANNELS", "FORCE_SUB_LINKS", mode="before", check_fields=False
    )
    @classmethod
    def parse_env_list_fields(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, (int, float)):
            return [int(value)]
        if isinstance(value, str):
            clean_str = value.strip("[]'\" ")
            if not clean_str:
                return []
            items = []
            for item in clean_str.split(","):
                item_str = item.strip()
                if item_str.lstrip("-").isdigit():
                    items.append(int(item_str))
                elif item_str:
                    items.append(item_str)
            return items
        if isinstance(value, list):
            return value
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
