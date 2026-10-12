from __future__ import annotations

import re
from datetime import timedelta

USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")
URL_RE = re.compile(r"^https?://[^\s<>]{1,2040}$", re.IGNORECASE)
MENTION_RE = re.compile(r"^tg://user\?id=\d+$")


def parse_duration(value: str, *, maximum_hours: int = 720) -> timedelta:
    """Parse 30s, 15m, 2h, or 3d into a bounded positive duration."""
    match = re.fullmatch(r"\s*(\d{1,5})\s*([smhd])\s*", value.lower())
    if not match:
        raise ValueError("Use a duration such as 30m, 2h, or 1d.")
    amount = int(match.group(1))
    factors = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    seconds = amount * factors[match.group(2)]
    if amount < 1 or seconds > maximum_hours * 3600:
        raise ValueError(f"Duration must be between 1 second and {maximum_hours} hours.")
    return timedelta(seconds=seconds)


def valid_link(value: str) -> bool:
    return bool(URL_RE.fullmatch(value.strip()))


def clean_text(value: str, maximum: int = 1000) -> str:
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"Text must contain 1–{maximum} characters.")
    return value


def parse_user_id(value: str) -> int | None:
    value = value.strip()
    if value.isdecimal():
        user_id = int(value)
        return user_id if user_id > 0 else None
    if USERNAME_RE.fullmatch(value):
        return None
    raise ValueError("Reply to a user or provide a numeric Telegram user ID / @username.")
