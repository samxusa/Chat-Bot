from __future__ import annotations

import logging
from datetime import datetime, timezone

from database.groups import get_settings
from database.statistics import record_event
from utils.formatters import escape

log = logging.getLogger(__name__)


async def audit(client: object, chat_id: int, action: str, actor_id: int | None = None,
                target_id: int | None = None, details: str = "") -> None:
    safe_action, safe_details = escape(action), escape(details[:500])
    try:
        await record_event(chat_id, action, {"actor_id": actor_id, "target_id": target_id, "details": details[:500]})
        settings = await get_settings(chat_id)
        if settings.get("log_channel_id"):
            text = f"🧾 <b>{safe_action}</b>\nGroup: <code>{chat_id}</code>"
            if actor_id is not None:
                text += f"\nBy: <code>{actor_id}</code>"
            if target_id is not None:
                text += f"\nTarget: <code>{target_id}</code>"
            if safe_details:
                text += f"\n{safe_details}"
            await client.send_message(settings["log_channel_id"], text)
    except Exception:
        log.exception("Could not write audit log for %s", action)
