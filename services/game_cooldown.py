from __future__ import annotations

from datetime import datetime, timezone

from database.groups import get_settings
from database.mongo import collection


async def claim_game_turn(chat_id: int, user_id: int) -> bool:
    group = await get_settings(chat_id)
    now = datetime.now(timezone.utc)
    allowed_after = now.timestamp() - int(group["game_cooldown_seconds"])
    await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id)},
        {"$setOnInsert": {"xp": 0, "aura": 0, "level": 1, "message_count": 0}},
        upsert=True,
    )
    result = await collection("users").update_one(
        {"chat_id": int(chat_id), "user_id": int(user_id),
         "$or": [{"last_game_at": {"$exists": False}}, {"last_game_at": {"$lte": allowed_after}}]},
        {"$set": {"last_game_at": now.timestamp()}},
    )
    return result.modified_count > 0
