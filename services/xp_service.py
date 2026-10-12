from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta, timezone

from database.groups import get_settings
from database.users import award_xp, increment_stat, update_identity
from database.mongo import collection
from pymongo import ReturnDocument


def level_for_xp(xp: int) -> int:
    return max(1, math.isqrt(max(0, int(xp)) // 100) + 1)


def fight_winner(challenger_score: int, target_score: int) -> int:
    """Return 0 for a draw, 1 if the challenger wins, and 2 if the target wins."""
    return 0 if challenger_score == target_score else (1 if challenger_score > target_score else 2)


async def record_message(chat_id: int, user: object, *, message_text: str = "") -> None:
    if getattr(user, "is_bot", False):
        return
    settings = await get_settings(chat_id)
    await update_identity(chat_id, user.id, user.first_name or "Member", user.username)
    now = datetime.now(timezone.utc)
    if not settings["xp_enabled"]:
        await collection("users").update_one(
            {"chat_id": int(chat_id), "user_id": int(user.id)},
            {"$inc": {"message_count": 1}, "$set": {"last_activity": now}},
        )
        return
    result = await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user.id),
         "$or": [{"last_xp_at": {"$exists": False}},
                 {"last_xp_at": {"$lte": now.timestamp() - int(settings["xp_cooldown_seconds"])}}]},
        {"$inc": {"message_count": 1, "xp": int(settings["xp_per_message"]), "aura": 1},
         "$set": {"last_activity": now, "last_xp_at": now.timestamp()}},
    )
    if result.modified_count == 0:
        await collection("users").update_one(
            {"chat_id": int(chat_id), "user_id": int(user.id)},
            {"$inc": {"message_count": 1}, "$set": {"last_activity": now}},
        )
    doc = await collection("users").find_one({"chat_id": int(chat_id), "user_id": int(user.id)})
    if doc:
        level = level_for_xp(doc.get("xp", 0))
        achievements = []
        if doc.get("message_count", 0) >= 1:
            achievements.append("first_message")
        if doc.get("message_count", 0) >= 100:
            achievements.append("100_messages")
        if doc.get("message_count", 0) >= 1000:
            achievements.append("1000_messages")
        if doc.get("xp", 0) >= 1000:
            achievements.append("1000_xp")
        await collection("users").update_one(
            {"_id": doc["_id"]},
            {"$set": {"level": level}, "$addToSet": {"achievements": {"$each": achievements}}},
        )


async def award_game(chat_id: int, user_id: int, points: int, *, aura: int = 0) -> bool:
    settings = await get_settings(chat_id)
    if not settings["xp_enabled"]:
        return False
    await award_xp(chat_id, user_id, points, aura)
    return True


async def daily_reward(chat_id: int, user_id: int) -> tuple[bool, int, int]:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$setOnInsert": {"xp": 0, "aura": 0, "level": 1, "message_count": 0, "daily_streak": 0}},
        upsert=True,
    )
    doc = await collection("users").find_one({"chat_id": int(chat_id), "user_id": int(user_id)})
    if doc and doc.get("last_daily") == today:
        return False, 0, int(doc.get("daily_streak", 0))
    streak = (int(doc.get("daily_streak", 0)) + 1) if doc and doc.get("last_daily") == yesterday else 1
    reward = 25 + min(streak, 7) * 5 + secrets.randbelow(11)
    claimed = await collection("users").find_one_and_update(
        {"chat_id": int(chat_id), "user_id": int(user_id), "last_daily": {"$ne": today}},
        {"$set": {"last_daily": today, "daily_streak": streak}, "$inc": {"xp": reward}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        latest = await collection("users").find_one({"chat_id": int(chat_id), "user_id": int(user_id)})
        return False, 0, int((latest or {}).get("daily_streak", 0))
    await increment_stat(chat_id, user_id, "daily_claims")
    await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$set": {"level": level_for_xp(int(claimed.get("xp", 0)))}},
    )
    return True, reward, streak
