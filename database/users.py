from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from database.mongo import collection


async def get_user(chat_id: int, user_id: int) -> dict[str, Any]:
    return await collection("users").find_one({"chat_id": int(chat_id), "user_id": int(user_id)}) or {
        "chat_id": int(chat_id), "user_id": int(user_id), "xp": 0, "aura": 0,
        "level": 1, "message_count": 0, "achievements": [], "daily_streak": 0,
    }


async def update_identity(chat_id: int, user_id: int, first_name: str, username: str | None) -> None:
    await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$set": {"first_name": first_name[:128], "username": username},
         "$setOnInsert": {"xp": 0, "aura": 0, "level": 1, "message_count": 0, "achievements": [], "daily_streak": 0}},
        upsert=True,
    )


async def award_xp(chat_id: int, user_id: int, xp: int, aura: int = 0, *, count_message: bool = False) -> dict[str, Any]:
    inc: dict[str, int] = {"xp": max(0, int(xp))}
    if aura:
        inc["aura"] = int(aura)
    if count_message:
        inc["message_count"] = 1
    doc = await collection("users").find_one_and_update(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$inc": inc, "$setOnInsert": {"level": 1, "achievements": [], "daily_streak": 0},
         "$set": {"last_activity": datetime.now(timezone.utc)}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    level = max(1, int((int(doc.get("xp", 0)) // 100) ** 0.5) + 1)
    if level != doc.get("level", 1):
        await collection("users").update_one({"_id": doc["_id"]}, {"$set": {"level": level}})
        doc["level"] = level
    return doc


async def top_users(chat_id: int, field: str = "xp", limit: int = 10) -> list[dict[str, Any]]:
    if field not in {"xp", "aura", "message_count"}:
        raise ValueError("Unsupported ranking field")
    cursor = collection("users").find({"chat_id": int(chat_id)}).sort(field, -1).limit(max(1, min(limit, 50)))
    return await cursor.to_list(length=max(1, min(limit, 50)))


async def increment_stat(chat_id: int, user_id: int, field: str, amount: int = 1) -> None:
    if field not in {"wins", "losses", "daily_claims", "games_played"}:
        raise ValueError("Unsupported user statistic")
    await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$inc": {field: amount}, "$setOnInsert": {"xp": 0, "aura": 0, "level": 1, "message_count": 0}},
        upsert=True,
    )
