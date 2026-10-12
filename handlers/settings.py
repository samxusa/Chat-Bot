"""Command alternatives for configurable group filters and service-message cleanup."""

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.groups import get_settings, set_setting
from services.permissions import can_manage
from utils.abuse_words import DEFAULT_ABUSE_TERMS
from utils.formatters import escape

FILTERS = {
    "abuse": "abuse_filter",
    "flood": "anti_flood",
    "links": "spam_links",
}


def register(app, settings: Settings) -> None:
    async def filter_toggle(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Only this group's admins can change filters.")
            return
        parts = message.text.lower().split()
        if len(parts) != 3 or parts[1] not in FILTERS or parts[2] not in {"on", "off"}:
            await message.reply_text("Usage: /filters abuse|flood|links on|off")
            return
        await set_setting(message.chat.id, FILTERS[parts[1]], parts[2] == "on")
        await message.reply_text(f"{parts[1].title()} filter is {parts[2]} for this group.")

    async def abuse_words(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Only this group's admins can edit the abuse list.")
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2 or parts[1].lower() not in {"add", "remove", "list", "reset"}:
            await message.reply_text("Usage: /abusewords add|remove|list|reset [term]")
            return
        config = await get_settings(message.chat.id)
        terms = list(config.get("abuse_terms") or DEFAULT_ABUSE_TERMS)
        action = parts[1].lower()
        if action == "list":
            safe = [escape(term) for term in terms[:80]]
            await message.reply_text("Configured terms: " + (", ".join(safe) if safe else "(none)"))
            return
        if action == "reset":
            await set_setting(message.chat.id, "abuse_terms", [])
            await message.reply_text("The default Hindi/Hinglish/English starter list is active.")
            return
        if len(parts) < 3:
            await message.reply_text(f"Usage: /abusewords {action} <term>")
            return
        term = parts[2].strip().casefold()
        if len(term) < 2 or len(term) > 40:
            await message.reply_text("Terms must contain 2–40 characters.")
            return
        if action == "add" and term not in terms:
            terms.append(term)
        elif action == "remove":
            terms = [item for item in terms if item.casefold() != term]
        await set_setting(message.chat.id, "abuse_terms", terms[:200])
        await message.reply_text(f"Abuse filter list updated ({len(terms)} terms).")

    async def service_cleanup(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Only this group's admins can change service-message cleanup.")
            return
        parts = message.text.lower().split()
        if len(parts) != 3 or parts[1] not in {"join", "leave"} or parts[2] not in {"on", "off"}:
            await message.reply_text("Usage: /servicecleanup join|leave on|off")
            return
        key = "delete_join_service" if parts[1] == "join" else "delete_leave_service"
        await set_setting(message.chat.id, key, parts[2] == "on")
        await message.reply_text(f"Join/leave service-message cleanup is {parts[2]}.")

    async def config_command(client, message):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        group = await get_settings(message.chat.id)
        await message.reply_text(
            "Group configuration\n"
            f"Abuse filter: {group['abuse_filter']} · Anti-flood: {group['anti_flood']} · Link filter: {group['spam_links']}\n"
            f"Warning limit: {group['warning_limit']} · Warning expiry: {group['warning_expiry_hours']}h\n"
            f"XP: {group['xp_enabled']} ({group['xp_per_message']}/message) · Game cooldown: {group['game_cooldown_seconds']}s\n"
            f"Welcome/goodbye: {group['welcome_enabled']}/{group['goodbye_enabled']}"
        )

    async def setting_value(client, message, key, low, high, suffix=""):
        if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings):
            await message.reply_text("Admins only.")
            return
        try:
            value = int(message.text.split()[1])
            if not low <= value <= high:
                raise ValueError
        except (IndexError, ValueError):
            await message.reply_text(f"Usage: /{key} <{low}–{high}>")
            return
        await set_setting(message.chat.id, key, value)
        await message.reply_text(f"{key.replace('_', ' ').title()} set to {value}{suffix}.")

    async def warning_expiry(client, message):
        await setting_value(client, message, "warning_expiry_hours", 0, 8760, " hours")

    async def mute_duration(client, message):
        await setting_value(client, message, "mute_minutes", 1, 1440, " minutes")

    for command, callback in {
        "filters": filter_toggle, "abusewords": abuse_words,
        "servicecleanup": service_cleanup, "groupconfig": config_command,
        "setwarningexpiry": warning_expiry, "setmuteduration": mute_duration,
    }.items():
        app.add_handler(MessageHandler(callback, filters.command(command) & filters.group))
