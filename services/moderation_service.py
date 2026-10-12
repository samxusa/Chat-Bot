from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pyrogram.types import ChatPermissions

from config import Settings
from database.groups import get_settings
from database.warnings import add_warning, clear_active_warnings
from services.logging_service import audit
from services.permissions import can_manage, is_protected
from utils.formatters import display_name
from utils.validators import parse_user_id


class ModerationError(Exception):
    pass


async def resolve_target(client: object, message: object) -> tuple[int, str]:
    reply = getattr(message, "reply_to_message", None)
    if reply and reply.from_user:
        return reply.from_user.id, display_name(reply.from_user)
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        raise ModerationError("Reply to a member or provide their numeric ID / @username.")
    raw = parts[1]
    try:
        numeric = parse_user_id(raw)
    except ValueError as exc:
        raise ModerationError(str(exc)) from exc
    if numeric is not None:
        return numeric, str(numeric)
    try:
        user = await client.get_users(raw)
        return user.id, display_name(user)
    except Exception as exc:
        raise ModerationError("I could not find that Telegram user.") from exc


async def require_admin(client: object, message: object, settings: Settings, *, owner_only: bool = False) -> None:
    if not message.from_user or not await can_manage(client, message.chat.id, message.from_user.id, settings, owner_only=owner_only):
        raise ModerationError("This command is limited to the group owner/admins." if not owner_only else "This command is owner-only.")


async def warn_member(client: object, chat_id: int, target_id: int, actor_id: int, reason: str, config: Settings) -> tuple[int, bool]:
    if await is_protected(client, chat_id, target_id, config):
        raise ModerationError("I cannot warn a configured owner or group administrator.")
    group = await get_settings(chat_id)
    count, _ = await add_warning(chat_id, target_id, actor_id, reason, int(group["warning_expiry_hours"]))
    banned = False
    if count >= int(group["warning_limit"]):
        await client.ban_chat_member(chat_id, target_id)
        await clear_active_warnings(chat_id, target_id)
        banned = True
        await audit(client, chat_id, "automatic_ban", actor_id, target_id, f"Reached {count} active warnings")
    await audit(client, chat_id, "warning", actor_id, target_id, reason)
    return count, banned


async def mute_member(client: object, chat_id: int, target_id: int, actor_id: int, duration: timedelta, config: Settings) -> None:
    if await is_protected(client, chat_id, target_id, config):
        raise ModerationError("I cannot mute a configured owner or group administrator.")
    until = datetime.now(timezone.utc) + duration
    await client.restrict_chat_member(chat_id, target_id, ChatPermissions(can_send_messages=False), until_date=until)
    await audit(client, chat_id, "mute", actor_id, target_id, f"Until {until.isoformat()}")


async def ban_member(client: object, chat_id: int, target_id: int, actor_id: int, config: Settings, action: str = "ban") -> None:
    if await is_protected(client, chat_id, target_id, config):
        raise ModerationError("I cannot moderate a configured owner or group administrator.")
    await client.ban_chat_member(chat_id, target_id)
    await audit(client, chat_id, action, actor_id, target_id)
