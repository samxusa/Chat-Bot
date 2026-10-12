from __future__ import annotations

import logging
from datetime import timedelta

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import ChatPermissions

from config import Settings
from database.groups import get_settings
from database.warnings import get_warnings
from services.moderation_service import (
    ModerationError, ban_member, mute_member, require_admin, resolve_target, warn_member,
)
from utils.formatters import display_name, human_duration
from utils.formatters import escape
from utils.validators import parse_duration

log = logging.getLogger(__name__)


async def _run_admin(client, message, settings: Settings, operation) -> None:
    try:
        await require_admin(client, message, settings)
        await operation()
    except ModerationError as exc:
        await message.reply_text(str(exc))
    except Exception:
        log.exception("Moderation command failed")
        await message.reply_text("That moderation action failed. Check my admin permissions and try again.")


def register(app, settings: Settings) -> None:
    async def warn_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            parts = message.text.split(maxsplit=2)
            reason_index = 1 if message.reply_to_message else 2
            reason = parts[reason_index] if len(parts) > reason_index else "No reason given"
            count, banned = await warn_member(client, message.chat.id, target, message.from_user.id, reason, settings)
            group = await get_settings(message.chat.id)
            suffix = f" · {count}/{group['warning_limit']} active"
            if banned:
                suffix += " · threshold reached; member banned"
            await message.reply_text(f"⚠️ {escape(name)} was warned. {escape(reason[:250])}{suffix}")
        await _run_admin(client, message, settings, action)

    async def warnings_cmd(client, message):
        try:
            if message.reply_to_message and message.reply_to_message.from_user:
                target = message.reply_to_message.from_user.id
            elif message.from_user and len(message.text.split()) > 1:
                target, _ = await resolve_target(client, message)
            elif message.from_user:
                target = message.from_user.id
            else:
                await message.reply_text("Reply to a member or provide their ID.")
                return
            if target != getattr(message.from_user, "id", None):
                await require_admin(client, message, settings)
            count, history, total = await get_warnings(message.chat.id, target)
            lines = [f"Warnings for <code>{target}</code>: <b>{count} active</b> · {total} total"]
            for item in history[:8]:
                at = item.get("at")
                stamp = at.strftime("%Y-%m-%d %H:%M UTC") if at else "unknown time"
                lines.append(f"• {stamp}: {escape((item.get('reason') or 'No reason')[:160])}")
            await message.reply_text("\n".join(lines))
        except ModerationError as exc:
            await message.reply_text(str(exc))
        except Exception:
            log.exception("Could not read warning history")
            await message.reply_text("I couldn't load that warning history.")

    async def mute_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            parts = message.text.split(maxsplit=3)
            duration = timedelta(minutes=int((await get_settings(message.chat.id))["mute_minutes"]))
            reason = "No reason given"
            duration_index = 1 if message.reply_to_message else 2
            reason_index = duration_index + 1
            if len(parts) > duration_index:
                try:
                    duration = parse_duration(parts[duration_index])
                    reason = parts[reason_index] if len(parts) > reason_index else reason
                except ValueError:
                    reason = " ".join(parts[duration_index:])
            await mute_member(client, message.chat.id, target, message.from_user.id, duration, settings)
            await message.reply_text(f"🔇 {escape(name)} muted for {human_duration(int(duration.total_seconds()))}. {escape(reason[:200])}")
        await _run_admin(client, message, settings, action)

    async def unmute_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            supported = ChatPermissions().__dict__
            fields = {
                "can_send_messages", "can_send_media_messages", "can_send_audios", "can_send_documents",
                "can_send_photos", "can_send_videos", "can_send_video_notes", "can_send_voice_notes",
                "can_send_polls", "can_send_other_messages", "can_add_web_page_previews",
            }
            permissions = ChatPermissions(**{key: True for key in fields if key in supported})
            await client.restrict_chat_member(message.chat.id, target, permissions=permissions)
            from services.logging_service import audit
            await audit(client, message.chat.id, "unmute", message.from_user.id, target)
            await message.reply_text(f"🔊 {escape(name)} can speak again.")
        await _run_admin(client, message, settings, action)

    async def ban_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            parts = message.text.split(maxsplit=2)
            reason_index = 1 if message.reply_to_message else 2
            reason = parts[reason_index] if len(parts) > reason_index else ""
            await ban_member(client, message.chat.id, target, message.from_user.id, settings)
            await message.reply_text(f"🔨 {escape(name)} was banned." + (f" Reason: {escape(reason[:250])}" if reason else ""))
        await _run_admin(client, message, settings, action)

    async def unban_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            await client.unban_chat_member(message.chat.id, target, only_if_banned=True)
            from services.logging_service import audit
            await audit(client, message.chat.id, "unban", message.from_user.id, target)
            await message.reply_text(f"✅ {escape(name)} was unbanned.")
        await _run_admin(client, message, settings, action)

    async def kick_cmd(client, message):
        async def action():
            target, name = await resolve_target(client, message)
            await ban_member(client, message.chat.id, target, message.from_user.id, settings, action="kick")
            await client.unban_chat_member(message.chat.id, target, only_if_banned=True)
            await message.reply_text(f"👢 {escape(name)} was removed from the group.")
        await _run_admin(client, message, settings, action)

    async def purge_cmd(client, message):
        async def action():
            if not message.reply_to_message:
                raise ModerationError("Reply to the first message to delete, optionally followed by a count (1–100).")
            parts = message.text.split()
            count = 1
            if len(parts) > 1:
                try:
                    count = max(1, min(100, int(parts[1])))
                except ValueError as exc:
                    raise ModerationError("Count must be from 1 to 100.") from exc
            start = message.reply_to_message.id
            ids = list(range(start, min(start + count, message.id)))
            if message.id not in ids:
                ids.append(message.id)
            ids = ids[-100:]
            await client.delete_messages(message.chat.id, ids)
            from services.logging_service import audit
            await audit(client, message.chat.id, "purge", message.from_user.id, details=f"Deleted up to {len(ids)} messages")
        await _run_admin(client, message, settings, action)

    commands = {
        "warn": warn_cmd, "warnings": warnings_cmd, "mute": mute_cmd, "unmute": unmute_cmd,
        "ban": ban_cmd, "unban": unban_cmd, "kick": kick_cmd, "purge": purge_cmd,
    }
    for command, callback in commands.items():
        app.add_handler(MessageHandler(callback, filters.command(command) & filters.group))
