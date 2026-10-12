from __future__ import annotations

import html
from datetime import datetime, timezone


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{escape(name)}</a>'


def display_name(user: object) -> str:
    return str(getattr(user, "first_name", None) or getattr(user, "username", None) or "member")


def human_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return f"{seconds // 86400}d"
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
