from __future__ import annotations

from pyrogram.enums import ChatMemberStatus

from config import Settings

ADMIN_STATUSES = {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}


def is_privileged_status(status: object) -> bool:
    return status in ADMIN_STATUSES or str(status).lower() in {"owner", "administrator", "chatmemberstatus.owner", "chatmemberstatus.administrator"}


async def is_owner(user_id: int, settings: Settings) -> bool:
    return int(user_id) in settings.owner_ids


async def is_group_owner(client: object, chat_id: int, user_id: int, settings: Settings) -> bool:
    if await is_owner(user_id, settings):
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER or str(member.status).lower() in {"owner", "chatmemberstatus.owner"}
    except Exception:
        return False


async def is_chat_admin(client: object, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return is_privileged_status(member.status)
    except Exception:
        return False


async def can_manage(client: object, chat_id: int, user_id: int, settings: Settings, *, owner_only: bool = False) -> bool:
    if await is_group_owner(client, chat_id, user_id, settings):
        return True
    if owner_only:
        return False
    return await is_chat_admin(client, chat_id, user_id)


async def is_protected(client: object, chat_id: int, user_id: int, settings: Settings) -> bool:
    if await is_group_owner(client, chat_id, user_id, settings):
        return True
    return await is_chat_admin(client, chat_id, user_id)
