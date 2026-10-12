from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def fight_keyboard(fight_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Accept fight ⚔️", callback_data=f"fight:{fight_id}")]])
