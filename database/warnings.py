from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from database.mongo import collection


def active_count(doc: dict[str, Any] | None, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return sum(1 for item in (doc or {}).get("active", []) if item.get("expires_at") is None or item["expires_at"] > now)


async def add_warning(chat_id: int, user_id: int, by_user_id: int, reason: str, expiry_hours: int = 0) -> tuple[int, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=expiry_hours) if expiry_hours > 0 else None
    warning = {"by": int(by_user_id), "reason": reason[:500], "at": now, "expires_at": expires}
    valid_active = {
        "$filter": {
            "input": {"$ifNull": ["$active", []]}, "as": "w",
            "cond": {"$or": [{"$eq": ["$$w.expires_at", None]}, {"$gt": ["$$w.expires_at", now]}]},
        }
    }
    doc = await collection("warnings").find_one_and_update(
        {"_id": f"{int(chat_id)}:{int(user_id)}"},
        [{"$set": {"chat_id": int(chat_id), "user_id": int(user_id),
                   "active": {"$concatArrays": [valid_active, [warning]]},
                   "total": {"$add": [{"$ifNull": ["$total", 0]}, 1]}}}],
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    await collection("warning_history").insert_one({
        "chat_id": int(chat_id), "user_id": int(user_id), **warning,
    })
    return active_count(doc, now), doc


async def get_warnings(chat_id: int, user_id: int) -> tuple[int, list[dict[str, Any]], int]:
    doc = await collection("warnings").find_one({"_id": f"{int(chat_id)}:{int(user_id)}"}) or {}
    now = datetime.now(timezone.utc)
    active = [item for item in doc.get("active", []) if item.get("expires_at") is None or item["expires_at"] > now]
    events = await collection("warning_history").find(
        {"chat_id": int(chat_id), "user_id": int(user_id)}
    ).sort("at", -1).limit(20).to_list(length=20)
    return len(active), events, int(doc.get("total", 0))


async def clear_active_warnings(chat_id: int, user_id: int) -> None:
    await collection("warnings").update_one(
        {"_id": f"{int(chat_id)}:{int(user_id)}"}, {"$set": {"active": []}}
    )
