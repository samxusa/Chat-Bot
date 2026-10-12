from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.groups import get_settings
from services.moderation_service import ModerationError, warn_member
from services.permissions import is_protected
from services.logging_service import audit
from utils.abuse_words import DEFAULT_ABUSE_TERMS, contains_abuse

log = logging.getLogger(__name__)


def register(app, settings: Settings) -> None:
    async def check_message(client, message):
        if not message.from_user or not message.text or message.text.startswith("/") or message.from_user.is_bot:
            return
        try:
            group = await get_settings(message.chat.id)
            if not group["abuse_filter"] or await is_protected(client, message.chat.id, message.from_user.id, settings):
                return
            terms = group.get("abuse_terms") or DEFAULT_ABUSE_TERMS
            if not contains_abuse(message.text, terms):
                return
            await message.delete()
            count, banned = await warn_member(client, message.chat.id, message.from_user.id, 0, "Abuse filter", settings)
            await audit(client, message.chat.id, "filter_abuse", 0, message.from_user.id, "Filtered message deleted")
            if not banned:
                await message.reply_text(f"Please keep the conversation respectful. Warning {count}/{group['warning_limit']}.")
        except ModerationError:
            return
        except Exception:
            log.exception("Abuse filter failed")

    app.add_handler(MessageHandler(check_message, filters.group & filters.text & ~filters.bot), group=1)
