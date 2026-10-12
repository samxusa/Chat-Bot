from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    abuse = "ON" if settings["abuse_filter"] else "OFF"
    spam = "ON" if settings["anti_flood"] else "OFF"
    links = "ON" if settings["spam_links"] else "OFF"
    welcome = "ON" if settings["welcome_enabled"] else "OFF"
    goodbye = "ON" if settings["goodbye_enabled"] else "OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Abuse filter: {abuse}", callback_data="set:abuse_filter"),
         InlineKeyboardButton(f"Anti-flood: {spam}", callback_data="set:anti_flood")],
        [InlineKeyboardButton(f"Link filter: {links}", callback_data="set:spam_links"),
         InlineKeyboardButton(f"Welcome: {welcome}", callback_data="set:welcome_enabled")],
        [InlineKeyboardButton(f"Goodbye: {goodbye}", callback_data="set:goodbye_enabled")],
        [InlineKeyboardButton(f"Warning limit: {settings['warning_limit']}", callback_data="set:warning_limit"),
         InlineKeyboardButton(f"XP: {settings['xp_enabled']}", callback_data="set:xp_enabled")],
        [InlineKeyboardButton("Refresh", callback_data="set:refresh")],
    ])
