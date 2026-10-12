from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from config import Settings

log = logging.getLogger(__name__)
client: AsyncMongoClient | None = None
db: Any = None


async def connect(settings: Settings) -> None:
    global client, db
    client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=12_000,
        connectTimeoutMS=12_000,
        tz_aware=True,
        appname="aresxchatbot",
    )
    await client.admin.command("ping")
    db = client[settings.mongodb_database]
    await ensure_indexes()
    log.info("Connected to MongoDB database %s", settings.mongodb_database)


async def ensure_indexes() -> None:
    if db is None:
        raise RuntimeError("MongoDB is not connected")
    await db.users.create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    await db.users.create_index([("chat_id", ASCENDING), ("xp", DESCENDING)])
    await db.users.create_index([("chat_id", ASCENDING), ("message_count", DESCENDING)])
    await db.groups.create_index([("_id", ASCENDING)], unique=True)
    await db.warnings.create_index([("_id", ASCENDING)], unique=True)
    await db.warning_history.create_index([("chat_id", ASCENDING), ("user_id", ASCENDING), ("at", DESCENDING)])
    await db.games.create_index([("_id", ASCENDING)], unique=True)
    await db.games.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.activity.create_index([("chat_id", ASCENDING), ("at", DESCENDING)])


async def close() -> None:
    global client, db
    if client is not None:
        await client.close()
        client = None
        db = None


def collection(name: str) -> Any:
    if db is None:
        raise RuntimeError("MongoDB is not connected")
    return db[name]
