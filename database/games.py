from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from database.mongo import collection


async def get_game(chat_id: int, game_type: str | None = None) -> dict[str, Any] | None:
    query: dict[str, Any] = {"chat_id": int(chat_id), "status": "active"}
    if game_type:
        query["type"] = game_type
    return await collection("games").find_one(query, sort=[("created_at", -1)])


async def set_game(chat_id: int, game_type: str, state: dict[str, Any], *, expires_at: datetime | None = None) -> None:
    now = datetime.now(timezone.utc)
    active_round = game_type in {"quiz", "wordgame"}
    game_id = f"{int(chat_id)}:active" if active_round else f"{int(chat_id)}:{game_type}"
    if active_round:
        await collection("games").find_one_and_update(
            {"_id": game_id, "$or": [{"status": {"$ne": "active"}}, {"expires_at": {"$lte": now}}]},
            {"$set": {"chat_id": int(chat_id), "type": game_type, "state": state,
                      "status": "active", "created_at": now, "expires_at": expires_at}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        return
    await collection("games").update_one(
        {"_id": game_id},
        {"$set": {"chat_id": int(chat_id), "type": game_type, "state": state,
                  "status": "active", "created_at": now, "expires_at": expires_at}},
        upsert=True,
    )


async def finish_game(chat_id: int, game_type: str) -> bool:
    active_round = game_type in {"quiz", "wordgame"}
    game_id = f"{int(chat_id)}:active" if active_round else f"{int(chat_id)}:{game_type}"
    result = await collection("games").update_one(
        {"_id": game_id, "type": game_type, "status": "active"},
        {"$set": {"status": "finished", "finished_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0
