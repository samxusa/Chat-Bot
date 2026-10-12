from __future__ import annotations

from datetime import datetime, timezone

from database.mongo import collection


async def group_summary(chat_id: int) -> dict[str, int]:
    users = collection("users")
    total = await users.count_documents({"chat_id": int(chat_id)})
    messages = await users.aggregate([
        {"$match": {"chat_id": int(chat_id)}},
        {"$group": {"_id": None, "count": {"$sum": "$message_count"}, "xp": {"$sum": "$xp"}}},
    ]).to_list(length=1)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    active = await users.count_documents({"chat_id": int(chat_id), "last_activity": {"$gte": today}})
    row = messages[0] if messages else {}
    return {"members_tracked": total, "messages": int(row.get("count", 0)), "xp": int(row.get("xp", 0)), "active_today": active}


async def record_event(chat_id: int, event: str, details: dict | None = None) -> None:
    await collection("activity").insert_one({
        "chat_id": int(chat_id), "event": event[:80], "details": details or {},
        "at": datetime.now(timezone.utc),
    })
