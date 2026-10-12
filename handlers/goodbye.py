from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.groups import get_settings, set_setting
from services.permissions import can_manage
from handlers.welcome import _render

log = logging.getLogger(__name__)


def register(app, settings: Settings) -> None:
    async def setgoodbye(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or len(parts[1]) > 1000:
            await message.reply_text("Usage: /setgoodbye Goodbye {first_name}!")
            return
        await set_setting(message.chat.id, "goodbye_text", parts[1].strip())
        await message.reply_text("Goodbye message saved.")

    async def toggle(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.lower().split()
        if len(parts) != 2 or parts[1] not in {"on", "off"}:
            await message.reply_text("Usage: /goodbye on|off")
            return
        await set_setting(message.chat.id, "goodbye_enabled", parts[1] == "on")
        await message.reply_text(f"Goodbye messages are {parts[1]}.")

    async def left_member(client, message):
        try:
            config = await get_settings(message.chat.id)
            user = message.left_chat_member
            if user and not user.is_bot and config["goodbye_enabled"]:
                text = _render(config["goodbye_text"], user, message.chat, getattr(message.chat, "members_count", 0) or 0)
                await message.reply_text(text)
            if config["delete_leave_service"]:
                await message.delete()
        except Exception:
            log.exception("Goodbye handler failed")

    app.add_handler(MessageHandler(setgoodbye, filters.command("setgoodbye") & filters.group))
    app.add_handler(MessageHandler(toggle, filters.command("goodbye") & filters.group))
    app.add_handler(MessageHandler(left_member, filters.left_chat_member), group=4)
