from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.users import get_user
from utils.formatters import display_name, escape

log = logging.getLogger(__name__)


def register(app, settings: Settings) -> None:
    async def aura(client, message):
        try:
            user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
            if not user:
                await message.reply_text("Reply to a member or use /aura.")
                return
            stats = await get_user(message.chat.id, user.id)
            await message.reply_text(f"✨ {escape(display_name(user))} has {stats.get('aura', 0)} aura.")
        except Exception:
            log.exception("Aura command failed")
            await message.reply_text("Could not load aura.")

    app.add_handler(MessageHandler(aura, filters.command("aura") & filters.group))
