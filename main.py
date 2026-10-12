from __future__ import annotations

import asyncio
import functools
import logging

from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

from config import load_settings
from database import mongo
from database.groups import set_default_warning_limit
from handlers import (
    abuse_filter, activity, admin, anti_spam, aura, chatfight, goodbye, help,
    minigames, moderation, quiz, rankings, settings as group_settings,
    social, welcome, wordgame,
)
from services.scheduler import start_job, stop_jobs
from database.mongo import collection
from datetime import datetime, timezone


class SafeHandlerRegistrar:
    """Wrap registered callbacks so unexpected exceptions never kill update workers."""

    def __init__(self, client: Client):
        self.client = client

    def add_handler(self, handler, group: int = 0):
        original = handler.callback

        @functools.wraps(original)
        async def safe_callback(client, update):
            try:
                return await original(client, update)
            except FloodWait as exc:
                delay = max(1, int(exc.value))
                logging.getLogger(__name__).warning("Telegram FloodWait for %s seconds", delay)
                await asyncio.sleep(min(delay, 60))
            except Exception:
                logging.getLogger(__name__).exception("Unhandled %s callback error", type(update).__name__)
                try:
                    update_message = getattr(update, "message", None)
                    if hasattr(update, "answer") and update_message is not None:
                        await update.answer("That action failed safely. Please try again.", show_alert=True)
                    elif hasattr(update, "reply_text"):
                        await update.reply_text("That action failed safely. Check the bot's permissions and try again.")
                except Exception:
                    logging.getLogger(__name__).debug("Could not send safe error notice")

        handler.callback = safe_callback
        return self.client.add_handler(handler, group=group)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def cleanup_expired_games() -> None:
    now = datetime.now(timezone.utc)
    await collection("games").update_many(
        {"status": {"$in": ["active", "pending"]}, "expires_at": {"$lte": now}},
        {"$set": {"status": "expired", "finished_at": now}},
    )


async def run() -> None:
    config = load_settings()
    configure_logging(config.log_level)
    set_default_warning_limit(config.warning_limit)
    logger = logging.getLogger(__name__)
    await mongo.connect(config)

    app = None
    started = False
    try:
        app = Client(
            config.session_name,
            api_id=config.api_id,
            api_hash=config.api_hash,
            bot_token=config.bot_token,
            parse_mode=ParseMode.HTML,
            sleep_threshold=60,
            workers=16,
        )
        registrar = SafeHandlerRegistrar(app)
        for module in (
            help, moderation, admin, group_settings, welcome, goodbye, abuse_filter, aura,
            anti_spam, chatfight, quiz, wordgame, minigames, social, rankings, activity,
        ):
            module.register(registrar, config)
        start_job("expire-games", 60, cleanup_expired_games)
        await app.start()
        started = True
        me = await app.get_me()
        logger.info("Bot started as @%s (id=%s)", me.username or "unknown", me.id)
        await idle()
    finally:
        await stop_jobs()
        try:
            if started and app is not None:
                await app.stop()
        finally:
            await mongo.close()
        logger.info("Bot shutdown complete")


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Shutdown requested")


if __name__ == "__main__":
    main()
