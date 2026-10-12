"""Environment-backed configuration. No credentials are stored in source control."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    mongodb_uri: str
    mongodb_database: str
    owner_ids: frozenset[int]
    log_level: str
    session_name: str
    warning_limit: int


def load_settings() -> Settings:
    try:
        api_id = int(_required("API_ID"))
    except ValueError as exc:
        raise ValueError("API_ID must be a positive integer") from exc
    if api_id <= 0:
        raise ValueError("API_ID must be a positive integer")
    api_hash = _required("API_HASH")
    bot_token = _required("BOT_TOKEN")
    if ":" not in bot_token:
        raise ValueError("BOT_TOKEN does not look like a BotFather token")
    owner_ids_raw = os.getenv("OWNER_IDS", "").strip()
    try:
        owner_ids = frozenset(int(item.strip()) for item in owner_ids_raw.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("OWNER_IDS must be comma-separated Telegram user IDs") from exc
    if not owner_ids or any(owner_id <= 0 for owner_id in owner_ids):
        raise ValueError("Set at least one trusted Telegram user ID in OWNER_IDS")
    mongodb_uri = _required("MONGODB_URI")
    if not mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("MONGODB_URI must use mongodb:// or mongodb+srv://")
    database = os.getenv("MONGODB_DATABASE", "ares_chatbot").strip()
    if not database:
        raise ValueError("MONGODB_DATABASE cannot be empty")
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        mongodb_uri=mongodb_uri,
        mongodb_database=database,
        owner_ids=owner_ids,
        log_level=level,
        session_name=os.getenv("SESSION_NAME", "aresxchatbot").strip() or "aresxchatbot",
        warning_limit=_int_env("DEFAULT_WARNING_LIMIT", 3, 1),
    )
