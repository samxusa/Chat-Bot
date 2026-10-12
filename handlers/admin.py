from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup

from config import Settings
from database.groups import get_settings, set_setting
from services.logging_service import audit
from services.permissions import can_manage
from utils.validators import valid_link

log = logging.getLogger(__name__)
PERMISSION_FIELDS = (
    "can_send_messages", "can_send_audios", "can_send_documents", "can_send_photos",
    "can_send_videos", "can_send_video_notes", "can_send_voice_notes", "can_send_polls",
    "can_send_other_messages", "can_add_web_page_previews", "can_change_info",
    "can_invite_users", "can_pin_messages", "can_manage_topics", "can_send_media_messages",
)


async def _member_can_edit(client, message, settings: Settings, owner_only: bool = False) -> bool:
    return bool(message.from_user and await can_manage(
        client, message.chat.id, message.from_user.id, settings, owner_only=owner_only
    ))


def _permissions_snapshot(permissions) -> dict[str, bool]:
    result = {}
    supported = getattr(ChatPermissions(), "__dict__", {})
    for field in PERMISSION_FIELDS:
        if field not in supported:
            continue
        value = getattr(permissions, field, None)
        if value is not None:
            result[field] = bool(value)
    return result


def register(app, settings: Settings) -> None:
    async def lockdown(client, message):
        if not await _member_can_edit(client, message, settings, owner_only=True):
            await message.reply_text("Only the Telegram group owner or configured bot owner can use lockdown.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or parts[1].strip().lower() != "confirm":
            await message.reply_text(
                "Lockdown will prevent ordinary members from sending messages. Admins can still coordinate. "
                "Run <code>/lockdown confirm</code> to apply.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Confirm lockdown", callback_data="lockdown:confirm"),
                    InlineKeyboardButton("Cancel", callback_data="lockdown:cancel"),
                ]]),
            )
            return
        await apply_lockdown(client, message.chat.id, message.from_user.id, message)

    async def apply_lockdown(client, chat_id: int, actor_id: int, message=None, query=None):
        group = await get_settings(chat_id)
        if group.get("lockdown_permissions") is not None:
            reply = "Lockdown is already active."
            if query:
                await query.answer(reply, show_alert=True)
            elif message:
                await message.reply_text(reply)
            return
        chat = await client.get_chat(chat_id)
        snapshot = _permissions_snapshot(getattr(chat, "permissions", None))
        if not snapshot:
            raise RuntimeError("Telegram did not return the current group permissions, so lockdown was not changed.")
        await set_setting(chat_id, "lockdown_permissions", snapshot)
        try:
            supported = getattr(ChatPermissions(), "__dict__", {})
            kwargs = {field: False for field in PERMISSION_FIELDS if field in supported}
            kwargs["can_send_messages"] = False
            await client.set_chat_permissions(chat_id, ChatPermissions(**kwargs))
        except Exception:
            await set_setting(chat_id, "lockdown_permissions", None)
            raise
        await audit(client, chat_id, "lockdown", actor_id, details="Member permissions saved for restoration")
        reply = "🔒 Lockdown is active. Use /unlock to restore the saved group permissions."
        if query:
            await query.message.edit_text(reply)
            await query.answer("Lockdown enabled")
        elif message:
            await message.reply_text(reply)

    async def unlock(client, message):
        if not await _member_can_edit(client, message, settings, owner_only=True):
            await message.reply_text("Only the Telegram group owner or configured bot owner can unlock the group.")
            return
        group = await get_settings(message.chat.id)
        snapshot = group.get("lockdown_permissions")
        if snapshot is None:
            await message.reply_text("There is no saved lockdown to restore.")
            return
        try:
            kwargs = {key: value for key, value in snapshot.items() if key in PERMISSION_FIELDS}
            await client.set_chat_permissions(message.chat.id, ChatPermissions(**kwargs))
            await set_setting(message.chat.id, "lockdown_permissions", None)
            await audit(client, message.chat.id, "unlock", message.from_user.id)
            await message.reply_text("🔓 Saved member permissions restored. Telegram may apply newer defaults to permission fields this bot API version did not expose.")
        except Exception:
            log.exception("Could not restore group permissions")
            await message.reply_text("I couldn't restore the saved permissions. Check my administrator permissions; the snapshot remains saved.")

    async def settings_cmd(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Only this group’s owner or an authorized administrator can change settings.")
            return
        from keyboards.admin_panel import settings_keyboard
        config = await get_settings(message.chat.id)
        await message.reply_text("⚙️ <b>Group settings</b>\nChanges apply only to this group.", reply_markup=settings_keyboard(config))

    async def setwarninglimit(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        try:
            value = int(message.text.split()[1])
            if not 1 <= value <= 20:
                raise ValueError
            await set_setting(message.chat.id, "warning_limit", value)
            await message.reply_text(f"Active warning limit set to {value}.")
        except (IndexError, ValueError):
            await message.reply_text("Usage: /setwarninglimit 3 (choose 1–20).")

    async def setlog(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: /setlog <channel_id> or /setlog off. Add me to the channel with permission to post.")
            return
        try:
            channel = None if parts[1].lower() == "off" else int(parts[1])
            await set_setting(message.chat.id, "log_channel_id", channel)
            await message.reply_text("Audit log channel updated." if channel else "Audit channel disabled.")
        except ValueError:
            await message.reply_text("Provide the numeric channel ID or /setlog off.")

    async def setlink(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.split(maxsplit=2)
        remove = len(parts) == 3 and parts[1].lower() == "remove"
        value = parts[2] if remove else (parts[1] if len(parts) == 2 else "")
        if not valid_link(value):
            await message.reply_text("Usage: /allowlink https://example.com or /allowlink remove https://example.com")
            return
        group = await get_settings(message.chat.id)
        links = list(group.get("allow_links", []))
        if remove:
            links = [link for link in links if link != value]
        elif value not in links:
            links.append(value)
        await set_setting(message.chat.id, "allow_links", links[:50])
        await message.reply_text("Link removed from this group's allow list." if remove else "Link added to this group's allow list.")

    async def setrules(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2 or not valid_link(parts[1]):
            await message.reply_text("Usage: /setrules https://example.com/rules")
            return
        await set_setting(message.chat.id, "rules_url", parts[1])
        await message.reply_text("Rules link saved.")

    async def setxp(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        parts = message.text.lower().split()
        if len(parts) != 2 or parts[1] not in {"on", "off"}:
            await message.reply_text("Usage: /xp on|off")
            return
        await set_setting(message.chat.id, "xp_enabled", parts[1] == "on")
        await message.reply_text(f"XP is {parts[1]} for this group.")

    async def setxpreward(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        try:
            value = int(message.text.split()[1])
            if not 0 <= value <= 50:
                raise ValueError
            await set_setting(message.chat.id, "xp_per_message", value)
            await message.reply_text(f"Message XP reward set to {value}.")
        except (IndexError, ValueError):
            await message.reply_text("Usage: /setxpreward <0–50>")

    async def setgamecooldown(client, message):
        if not await _member_can_edit(client, message, settings):
            await message.reply_text("Admins only.")
            return
        try:
            value = int(message.text.split()[1])
            if not 0 <= value <= 3600:
                raise ValueError
            await set_setting(message.chat.id, "game_cooldown_seconds", value)
            await message.reply_text(f"Game cooldown set to {value} seconds.")
        except (IndexError, ValueError):
            await message.reply_text("Usage: /setgamecooldown <0–3600 seconds>")

    async def callbacks(client, query):
        try:
            if not query.message or not query.from_user or not await can_manage(
                client, query.message.chat.id, query.from_user.id, settings
            ):
                await query.answer("Only this group's admins can change settings.", show_alert=True)
                return
            data = query.data or ""
            if data == "lockdown:cancel":
                await query.message.edit_text("Lockdown cancelled.")
                await query.answer()
                return
            if data == "lockdown:confirm":
                if not await can_manage(client, query.message.chat.id, query.from_user.id, settings, owner_only=True):
                    await query.answer("Owner-only action.", show_alert=True)
                    return
                await apply_lockdown(client, query.message.chat.id, query.from_user.id, query=query)
                return
            key = data.removeprefix("set:")
            group = await get_settings(query.message.chat.id)
            if key == "refresh":
                from keyboards.admin_panel import settings_keyboard
                await query.message.edit_reply_markup(settings_keyboard(group))
                await query.answer("Settings refreshed")
                return
            allowed = {"abuse_filter", "anti_flood", "spam_links", "welcome_enabled", "goodbye_enabled", "xp_enabled"}
            if key == "warning_limit":
                next_value = int(group["warning_limit"]) % 10 + 1
                await set_setting(query.message.chat.id, key, next_value)
            elif key in allowed:
                await set_setting(query.message.chat.id, key, not bool(group[key]))
            else:
                await query.answer("Unknown setting.", show_alert=True)
                return
            group = await get_settings(query.message.chat.id)
            from keyboards.admin_panel import settings_keyboard
            await query.message.edit_reply_markup(settings_keyboard(group))
            await query.answer("Saved for this group")
        except Exception:
            log.exception("Settings callback failed")
            await query.answer("Could not save that setting.", show_alert=True)

    for command, callback in {
        "lockdown": lockdown, "unlock": unlock, "settings": settings_cmd,
        "setwarninglimit": setwarninglimit, "setlog": setlog, "allowlink": setlink,
        "setrules": setrules, "xp": setxp, "setxpreward": setxpreward,
        "setgamecooldown": setgamecooldown,
    }.items():
        app.add_handler(MessageHandler(callback, filters.command(command) & filters.group))
    app.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^(set:|lockdown:)")))
