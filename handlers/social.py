from __future__ import annotations

import logging
import secrets

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.mongo import collection
from services.game_cooldown import claim_game_turn
from services.xp_service import award_game
from utils.formatters import display_name, escape

log = logging.getLogger(__name__)


async def _target(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        try:
            return await client.get_users(parts[1])
        except Exception:
            return None
    return None


def _compatibility(first_id: int, second_id: int) -> int:
    # Stable, playful score (not a real relationship assessment).
    seed = f"{min(first_id, second_id)}:{max(first_id, second_id)}".encode()
    return int.from_bytes(__import__("hashlib").sha256(seed).digest()[:2], "big") % 101


def register(app, settings: Settings) -> None:
    async def ship(client, message):
        first = message.from_user
        second = await _target(client, message)
        if not first or not second or first.id == second.id or second.is_bot:
            await message.reply_text("Reply to another member or use /ship @username.")
            return
        if not await claim_game_turn(message.chat.id, first.id):
            await message.reply_text("Wait a moment before using this again.")
            return
        score = _compatibility(first.id, second.id)
        await message.reply_text(
            f"💞 {escape(display_name(first))} + {escape(display_name(second))}: <b>{score}%</b>\n"
            "Just for fun — not a real compatibility measure."
        )
        await award_game(message.chat.id, first.id, 1)

    async def lovepair(client, message):
        if not message.from_user:
            return
        if not await claim_game_turn(message.chat.id, message.from_user.id):
            await message.reply_text("Wait a moment before using this again.")
            return
        members = await collection("users").find(
            {"chat_id": message.chat.id, "user_id": {"$ne": message.from_user.id}}
        ).limit(100).to_list(length=100)
        members = [item for item in members if not item.get("is_bot")]
        if not members:
            await message.reply_text("I need some active members before I can pick a pair.")
            return
        one = secrets.choice(members)
        two = secrets.choice(members)
        if one["user_id"] == two["user_id"]:
            await message.reply_text("The randomizer picked the same person twice — try again.")
            return
        score = _compatibility(one["user_id"], two["user_id"])
        await message.reply_text(
            f"💘 Today's just-for-fun pair: {escape(one.get('first_name', 'Member'))} + "
            f"{escape(two.get('first_name', 'Member'))} — {score}%!\nEntertainment only."
        )
        await award_game(message.chat.id, message.from_user.id, 1)

    app.add_handler(MessageHandler(ship, filters.command("ship") & filters.group))
    app.add_handler(MessageHandler(lovepair, filters.command("lovepair") & filters.group))
