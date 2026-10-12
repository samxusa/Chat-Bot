from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.groups import get_settings
from services.logging_service import audit
from services.moderation_service import ModerationError, warn_member
from services.permissions import is_protected

log = logging.getLogger(__name__)
_activity: dict[tuple[int, int], deque[tuple[float, str]]] = defaultdict(deque)
_last_flag: dict[tuple[int, int], float] = {}
LINK_RE = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)


def _approved_link(link: str, allowed_links: list[str]) -> bool:
    candidate = link.strip().rstrip(".,!?)]}")
    if candidate.lower().startswith("www."):
        candidate = "https://" + candidate
    try:
        host = (urlsplit(candidate).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    if not host:
        return False
    for allowed in allowed_links:
        allowed = allowed.strip()
        if allowed.lower().startswith("www."):
            allowed = "https://" + allowed
        try:
            allowed_host = (urlsplit(allowed).hostname or "").casefold().rstrip(".")
        except ValueError:
            continue
        if allowed_host and (host == allowed_host or host.endswith("." + allowed_host)):
            return True
    return False


def register(app, settings: Settings) -> None:
    async def check_message(client, message):
        user = message.from_user
        if not user or user.is_bot or not message.text or message.text.startswith("/"):
            return
        try:
            config = await get_settings(message.chat.id)
            if await is_protected(client, message.chat.id, user.id, settings):
                return
            now = time.monotonic()
            if len(_activity) > 5000:
                expired_keys = [
                    item for item, entries in _activity.items()
                    if not entries or now - entries[-1][0] > 120
                ]
                for expired in expired_keys:
                    _activity.pop(expired, None)
                    _last_flag.pop(expired, None)
            key = (message.chat.id, user.id)
            text = " ".join(message.text.casefold().split())
            bucket = _activity[key]
            window = int(config["flood_window_seconds"])
            while bucket and now - bucket[0][0] > window:
                bucket.popleft()
            reason = None
            if config["anti_flood"]:
                bucket.append((now, text[:400]))
                if len(bucket) >= int(config["flood_limit"]):
                    reason = "Flood protection"
                elif sum(1 for _, recent in bucket if recent == text) >= int(config["repeat_limit"]):
                    reason = "Repeated message protection"
            if config["spam_links"]:
                links = LINK_RE.findall(message.text)
                allow = config.get("allow_links", [])
                if links and any(not _approved_link(link, allow) for link in links):
                    reason = reason or "Unapproved link"
            if not reason or now - _last_flag.get(key, 0) < 30:
                return
            _last_flag[key] = now
            await message.delete()
            count, banned = await warn_member(client, message.chat.id, user.id, 0, reason, settings)
            await audit(client, message.chat.id, "filter_spam", 0, user.id, reason)
            if not banned:
                await message.reply_text(f"Message removed: {reason}. Warning {count}/{config['warning_limit']}.")
        except ModerationError:
            return
        except Exception:
            log.exception("Anti-spam check failed")

    app.add_handler(MessageHandler(check_message, filters.group & filters.text & ~filters.bot), group=2)
