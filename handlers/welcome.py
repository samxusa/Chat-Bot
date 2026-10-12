from __future__ import annotations

import logging
import re

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Settings
from database.groups import get_settings
from keyboards.welcome_buttons import welcome_keyboard
from services.permissions import can_manage
from utils.validators import clean_text, valid_link
from utils.formatters import escape

log = logging.getLogger(__name__)
TOKENS = {"{first_name}", "{username}", "{chat_title}", "{members_count}"}


def _render(template: str, user, chat, count: int) -> str:
    name = user.first_name or "Member"
    username = f"@{user.username}" if user.username else "not set"
    title = chat.title or "the group"
    values = {
        "first_name": escape(name), "username": escape(username),
        "chat_title": escape(title), "members_count": str(int(count)),
    }
    return re.sub(
        r"\{([a-zA-Z_]+)\}",
        lambda match: values.get(match.group(1), match.group(0)),
        template,
    )[:4000]


def register(app, settings: Settings) -> None:
    async def setwelcome(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Only this group’s owner or an authorized administrator can change the welcome.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: /setwelcome Welcome {first_name} to {chat_title}!")
            return
        try:
            text = clean_text(parts[1], 1000)
            unknown = re.findall(r"\{([a-zA-Z_]+)\}", text)
            if any("{" + token + "}" not in TOKENS for token in unknown):
                raise ValueError("Supported tokens: {first_name}, {username}, {chat_title}, {members_count}.")
            await __import__("database.groups", fromlist=["set_setting"]).set_setting(message.chat.id, "welcome_text", text)
            await message.reply_text("Welcome message saved. Tokens: {first_name}, {username}, {chat_title}, {members_count}.")
        except ValueError as exc:
            await message.reply_text(str(exc))

    async def toggle(client, message, field):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.lower().split()
        if len(parts) != 2 or parts[1] not in {"on", "off"}:
            await message.reply_text(f"Usage: /{field.removesuffix('_enabled')} on|off")
            return
        await __import__("database.groups", fromlist=["set_setting"]).set_setting(message.chat.id, field, parts[1] == "on")
        await message.reply_text(f"{field.split('_')[0].title()} messages are {parts[1]}.")

    async def welcome_toggle(client, message):
        await toggle(client, message, "welcome_enabled")

    async def setphoto(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        if message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id
            await __import__("database.groups", fromlist=["set_setting"]).set_setting(message.chat.id, "welcome_photo", file_id)
            await message.reply_text("Welcome photo saved.")
        else:
            await message.reply_text("Reply to a photo with /setwelcomepic. Use /clearwelcomepic to remove it.")

    async def clearphoto(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        await __import__("database.groups", fromlist=["set_setting"]).set_setting(message.chat.id, "welcome_photo", None)
        await message.reply_text("Welcome photo cleared.")

    async def setbutton(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or "|" not in parts[1]:
            await message.reply_text("Usage: /addwelcomebutton Button label | https://example.com")
            return
        label, url = (part.strip() for part in parts[1].split("|", 1))
        if not label or len(label) > 64 or not valid_link(url):
            await message.reply_text("Use a button label of 1–64 characters and a valid HTTP(S) URL.")
            return
        from database.groups import set_setting
        config = await get_settings(message.chat.id)
        buttons = list(config.get("welcome_buttons", []))
        buttons.append({"text": label, "url": url})
        await set_setting(message.chat.id, "welcome_buttons", buttons[:8])
        await message.reply_text("Welcome button added (up to 8 buttons).")

    async def clearbuttons(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        from database.groups import set_setting
        await set_setting(message.chat.id, "welcome_buttons", [])
        await message.reply_text("Custom welcome buttons cleared.")

    async def welcome_member(client, message):
        try:
            config = await get_settings(message.chat.id)
            for user in message.new_chat_members or []:
                if user.is_bot or not config["welcome_enabled"]:
                    continue
                count = getattr(message.chat, "members_count", 0) or 0
                text = _render(config["welcome_text"], user, message.chat, count)
                markup = welcome_keyboard(config)
                photo = config.get("welcome_photo")
                if photo:
                    await client.send_photo(message.chat.id, photo, caption=text, reply_markup=markup)
                else:
                    await message.reply_text(text, reply_markup=markup)
            if config["delete_join_service"]:
                await message.delete()
        except Exception:
            log.exception("Welcome handler failed")

    app.add_handler(MessageHandler(setwelcome, filters.command("setwelcome") & filters.group))
    app.add_handler(MessageHandler(welcome_toggle, filters.command("welcome") & filters.group))
    app.add_handler(MessageHandler(setphoto, filters.command("setwelcomepic") & filters.group))
    app.add_handler(MessageHandler(clearphoto, filters.command("clearwelcomepic") & filters.group))
    app.add_handler(MessageHandler(setbutton, filters.command("addwelcomebutton") & filters.group))
    app.add_handler(MessageHandler(clearbuttons, filters.command("clearwelcomebuttons") & filters.group))
    app.add_handler(MessageHandler(welcome_member, filters.new_chat_members), group=4)
