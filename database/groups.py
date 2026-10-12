from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from database.mongo import collection

DEFAULTS: dict[str, Any] = {
    "warning_limit": 3,
    "warning_expiry_hours": 0,
    "mute_minutes": 30,
    "abuse_filter": True,
    "abuse_terms": [],
    "anti_flood": True,
    "flood_limit": 7,
    "flood_window_seconds": 8,
    "repeat_limit": 4,
    "spam_links": True,
    "allow_links": [],
    "xp_enabled": True,
    "xp_per_message": 5,
    "xp_cooldown_seconds": 60,
    "game_cooldown_seconds": 10,
    "welcome_enabled": True,
    "welcome_text": "Welcome {first_name} to {chat_title}! You are member #{members_count}.",
    "welcome_photo": None,
    "welcome_buttons": [],
    "goodbye_enabled": True,
    "goodbye_text": "Goodbye {first_name}!",
    "rules_url": None,
    "delete_join_service": False,
    "delete_leave_service": False,
    "log_channel_id": None,
    "lockdown_permissions": None,
}


def set_default_warning_limit(value: int) -> None:
    if not 1 <= int(value) <= 20:
        raise ValueError("Default warning limit must be from 1 to 20")
    DEFAULTS["warning_limit"] = int(value)


async def get_settings(chat_id: int) -> dict[str, Any]:
    doc = await collection("groups").find_one_and_update(
        {"_id": int(chat_id)},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    merged = deepcopy(DEFAULTS)
    merged.update({key: value for key, value in doc.items() if key != "_id"})
    return merged


async def set_setting(chat_id: int, key: str, value: Any) -> None:
    if key not in DEFAULTS and key not in {"lockdown_permissions"}:
        raise ValueError(f"Unsupported group setting: {key}")
    await collection("groups").update_one(
        {"_id": int(chat_id)}, {"$set": {key: value}, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True
    )


async def update_settings(chat_id: int, values: dict[str, Any]) -> None:
    if not values or any(key not in DEFAULTS and key != "lockdown_permissions" for key in values):
        raise ValueError("Invalid group setting update.")
    await collection("groups").update_one(
        {"_id": int(chat_id)},
        {"$set": values, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
