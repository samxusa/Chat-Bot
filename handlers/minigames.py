from __future__ import annotations

import logging
import secrets

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from services.game_cooldown import claim_game_turn
from services.xp_service import award_game

log = logging.getLogger(__name__)
BALL = [
    "Yes, definitely.", "The signs point to yes.", "Ask again later.",
    "Probably not.", "It is looking good.", "I wouldn't count on it.",
]


def register(app, settings: Settings) -> None:
    async def run_limited(client, message, reply):
        if message.from_user and not await claim_game_turn(message.chat.id, message.from_user.id):
            await message.reply_text("Wait a moment before playing again.")
            return
        await reply(client, message)

    async def rps(client, message):
        async def play(c, m):
            parts = m.text.lower().split()
            if len(parts) < 2 or parts[1] not in {"rock", "paper", "scissors", "🪨", "📄", "✂️"}:
                await m.reply_text("Usage: /rps rock|paper|scissors")
                return
            aliases = {"🪨": "rock", "📄": "paper", "✂️": "scissors"}
            player = aliases.get(parts[1], parts[1])
            bot = secrets.choice(["rock", "paper", "scissors"])
            result = "draw" if player == bot else ("win" if (player, bot) in {
                ("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")} else "lose")
            await m.reply_text(f"You: {player} · Bot: {bot} — {result.title()}!")
            await award_game(m.chat.id, m.from_user.id, 3 if result == "win" else 1)
        await run_limited(client, message, play)

    async def roll(client, message):
        async def play(c, m):
            parts = m.text.split()
            try:
                maximum = int(parts[1]) if len(parts) > 1 else 6
                if not 2 <= maximum <= 1_000_000:
                    raise ValueError
            except ValueError:
                await m.reply_text("Usage: /roll [maximum from 2 to 1000000]")
                return
            await m.reply_text(f"🎲 {secrets.randbelow(maximum) + 1} (1–{maximum})")
            await award_game(m.chat.id, m.from_user.id, 1)
        await run_limited(client, message, play)

    async def coinflip(client, message):
        async def play(c, m):
            await m.reply_text(f"🪙 {secrets.choice(['Heads', 'Tails'])}!")
            await award_game(m.chat.id, m.from_user.id, 1)
        await run_limited(client, message, play)

    async def eightball(client, message):
        async def play(c, m):
            if len(m.text.split()) < 2:
                await m.reply_text("Ask a question: /8ball will I win?")
                return
            await m.reply_text(f"🎱 {secrets.choice(BALL)}")
            await award_game(m.chat.id, m.from_user.id, 1)
        await run_limited(client, message, play)

    async def truth(client, message):
        async def play(c, m):
            prompts = ["What small thing always makes your day better?", "What is a skill you wish you had?", "What is a harmless fear you have?", "What song do you never skip?"]
            await m.reply_text("💬 Truth: " + secrets.choice(prompts))
            await award_game(m.chat.id, m.from_user.id, 1)
        await run_limited(client, message, play)

    async def dare(client, message):
        async def play(c, m):
            prompts = ["Share your current favorite song.", "Send a photo of something blue nearby.", "Give someone in the group a sincere compliment.", "Describe your day using only three emojis."]
            await m.reply_text("🎯 Dare (keep it safe and kind): " + secrets.choice(prompts))
            await award_game(m.chat.id, m.from_user.id, 1)
        await run_limited(client, message, play)

    for name, callback in {
        "rps": rps, "roll": roll, "coinflip": coinflip, "8ball": eightball,
        "truth": truth, "dare": dare,
    }.items():
        app.add_handler(MessageHandler(callback, filters.command(name) & filters.group))
