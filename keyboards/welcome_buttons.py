from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def welcome_keyboard(settings: dict) -> InlineKeyboardMarkup | None:
    rows = []
    for item in settings.get("welcome_buttons", [])[:8]:
        if isinstance(item, dict) and item.get("text") and item.get("url", "").startswith(("https://", "http://")):
            rows.append([InlineKeyboardButton(str(item["text"])[:64], url=item["url"])])
    if settings.get("rules_url", "").startswith(("https://", "http://")):
        rows.append([InlineKeyboardButton("📜 Group rules", url=settings["rules_url"])])
    return InlineKeyboardMarkup(rows) if rows else None
