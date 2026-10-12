from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pymongo.errors import DuplicateKeyError

from config import Settings
from database.games import get_game, set_game
from services.game_cooldown import claim_game_turn

log = logging.getLogger(__name__)
WORDS = ["planet", "garden", "stream", "puzzle", "silver", "rocket", "camera", "winter", "bright"]


def scramble_word(word: str) -> str:
    letters = list(word)
    for _ in range(8):
        secrets.SystemRandom().shuffle(letters)
        if "".join(letters) != word:
            break
    return "".join(letters)


def register(app, settings: Settings) -> None:
    async def wordgame(client, message):
        if not await claim_game_turn(message.chat.id, message.from_user.id):
            await message.reply_text("Wait a moment before starting another game.")
            return
        if await get_game(message.chat.id):
            await message.reply_text("A game is already active in this group.")
            return
        word = secrets.choice(WORDS)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=45)
        try:
            await set_game(message.chat.id, "wordgame", {
                "answer": word, "started_by": message.from_user.id,
            }, expires_at=deadline)
        except DuplicateKeyError:
            await message.reply_text("A game was started at the same time. Finish it before starting another.")
            return
        await message.reply_text(f"🔤 Unscramble this word in 45 seconds: <code>{scramble_word(word)}</code>\nUse /answer your answer")

    app.add_handler(MessageHandler(wordgame, filters.command("wordgame") & filters.group))
