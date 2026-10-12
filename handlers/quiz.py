from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pymongo.errors import DuplicateKeyError

from config import Settings
from database.games import finish_game, get_game, set_game
from services.game_cooldown import claim_game_turn
from services.xp_service import award_game

log = logging.getLogger(__name__)
QUESTIONS = [
    ("What is the capital of Japan?", "tokyo"),
    ("Which planet is known as the Red Planet?", "mars"),
    ("How many sides does a hexagon have?", "6"),
    ("What is the largest ocean on Earth?", "pacific"),
    ("What is 12 × 8?", "96"),
    ("Which gas do plants absorb from the air?", "carbon dioxide"),
]


def normalize_answer(value: str) -> str:
    return " ".join(value.casefold().strip().split()).strip(" .!?")


def register(app, settings: Settings) -> None:
    async def quiz(client, message):
        if not await claim_game_turn(message.chat.id, message.from_user.id):
            await message.reply_text("Wait a moment before starting another game.")
            return
        active = await get_game(message.chat.id)
        if active:
            await message.reply_text("A game is already active. Finish it with /answer or wait for it to expire.")
            return
        question, answer = secrets.choice(QUESTIONS)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=60)
        try:
            await set_game(message.chat.id, "quiz", {
                "question": question, "answer": answer, "started_by": message.from_user.id,
            }, expires_at=deadline)
        except DuplicateKeyError:
            await message.reply_text("A game was started at the same time. Finish it before starting another.")
            return
        await message.reply_text(f"🧠 <b>Quiz</b> · 60 seconds\n{question}\nReply with /answer your answer")

    async def answer(client, message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: /answer your answer")
            return
        game = await get_game(message.chat.id)
        if not game or game.get("type") not in {"quiz", "wordgame"}:
            await message.reply_text("There is no active quiz or word game.")
            return
        deadline = game.get("expires_at")
        if deadline and deadline <= datetime.now(timezone.utc):
            await finish_game(message.chat.id, game["type"])
            await message.reply_text("Time is up. Start another with /quiz or /wordgame.")
            return
        expected = normalize_answer(game["state"]["answer"])
        attempt = normalize_answer(parts[1])
        if attempt == expected:
            if not await finish_game(message.chat.id, game["type"]):
                await message.reply_text("That round has already ended.")
                return
            awarded = await award_game(message.chat.id, message.from_user.id, 15, aura=1)
            reward = " +15 XP, +1 aura." if awarded else " XP rewards are disabled in this group."
            await message.reply_text(f"✅ Correct, {message.from_user.first_name}!{reward}")
        else:
            await message.reply_text("Not quite — try again before time runs out.")

    app.add_handler(MessageHandler(quiz, filters.command("quiz") & filters.group))
    app.add_handler(MessageHandler(answer, filters.command("answer") & filters.group))
