from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pymongo import ReturnDocument

from config import Settings
from database.games import finish_game, set_game
from database.groups import get_settings
from database.mongo import collection
from database.users import increment_stat
from keyboards.game_buttons import fight_keyboard
from services.logging_service import audit
from services.game_cooldown import claim_game_turn
from services.xp_service import award_game, fight_winner
from utils.formatters import display_name, escape

log = logging.getLogger(__name__)


def register(app, settings: Settings) -> None:
    async def fight(client, message):
        if not message.from_user:
            return
        try:
            if not await claim_game_turn(message.chat.id, message.from_user.id):
                await message.reply_text("Wait a moment before starting another game.")
                return
            if message.reply_to_message and message.reply_to_message.from_user:
                target = message.reply_to_message.from_user
            else:
                parts = message.text.split(maxsplit=1)
                if len(parts) < 2:
                    await message.reply_text("Reply to a member with /fight or use /fight @username.")
                    return
                target = await client.get_users(parts[1])
            if target.is_bot or target.id == message.from_user.id:
                await message.reply_text("Pick another human member to challenge.")
                return
            cfg = await get_settings(message.chat.id)
            active = await collection("games").find_one({"chat_id": message.chat.id, "type": "fight", "status": "pending"})
            if active:
                await message.reply_text("There is already a pending fight in this group.")
                return
            expires = datetime.now(timezone.utc) + timedelta(minutes=5)
            fight_id = f"{message.chat.id}:fight"
            await collection("games").update_one(
                {"_id": fight_id},
                {"$set": {"chat_id": message.chat.id, "type": "fight", "status": "pending",
                          "state": {"challenger": message.from_user.id, "target": target.id,
                                    "challenger_name": display_name(message.from_user), "target_name": display_name(target)},
                          "created_at": datetime.now(timezone.utc), "expires_at": expires}},
                upsert=True,
            )
            await message.reply_text(
                f"⚔️ {escape(display_name(message.from_user))} challenges {escape(display_name(target))}! "
                "The winner earns XP; accept within 5 minutes.",
                reply_markup=fight_keyboard(fight_id),
            )
        except Exception:
            log.exception("Could not create fight")
            await message.reply_text("Could not start that fight. Check the username and try again.")

    async def accept_fight(client, message):
        if not message.from_user:
            return
        await resolve_fight(client, message.chat.id, message.from_user.id, message=message)

    async def resolve_fight(client, chat_id: int, user_id: int, message=None, query=None):
        doc = await collection("games").find_one({"_id": f"{chat_id}:fight", "type": "fight", "status": "pending"})
        if not doc:
            text = "No pending fight."
            if query:
                await query.answer(text, show_alert=True)
            elif message:
                await message.reply_text(text)
            return
        state = doc["state"]
        if user_id != int(state["target"]):
            text = "Only the challenged member can accept this fight."
            if query:
                await query.answer(text, show_alert=True)
            elif message:
                await message.reply_text(text)
            return
        if query is None and not await claim_game_turn(chat_id, user_id):
            await message.reply_text("Wait a moment before accepting another game.")
            return
        now = datetime.now(timezone.utc)
        updated = await collection("games").find_one_and_update(
            {"_id": doc["_id"], "status": "pending", "expires_at": {"$gt": now}},
            {"$set": {"status": "active", "started_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            await finish_game(chat_id, "fight")
            text = "That fight challenge expired."
            if query:
                await query.answer(text, show_alert=True)
            elif message:
                await message.reply_text(text)
            return
        first, second = secrets.randbelow(100) + 1, secrets.randbelow(100) + 1
        winner = fight_winner(first, second)
        if winner == 0:
            awarded_one = await award_game(chat_id, int(state["challenger"]), 5)
            awarded_two = await award_game(chat_id, int(state["target"]), 5)
            await increment_stat(chat_id, int(state["challenger"]), "games_played")
            await increment_stat(chat_id, int(state["target"]), "games_played")
            text = f"⚔️ Draw! Scores: {first}–{second}."
            if awarded_one and awarded_two:
                text += " Both fighters earn 5 XP."
            else:
                text += " XP rewards are disabled in this group."
        else:
            winner_id = int(state["challenger"] if winner == 1 else state["target"])
            loser_id = int(state["target"] if winner == 1 else state["challenger"])
            winner_name = state["challenger_name"] if winner == 1 else state["target_name"]
            awarded = await award_game(chat_id, winner_id, 20, aura=2)
            await increment_stat(chat_id, winner_id, "wins")
            await increment_stat(chat_id, loser_id, "losses")
            await increment_stat(chat_id, winner_id, "games_played")
            await increment_stat(chat_id, loser_id, "games_played")
            text = f"⚔️ {escape(winner_name)} wins! Scores: {first}–{second}."
            text += " +20 XP, +2 aura." if awarded else " XP rewards are disabled in this group."
        await finish_game(chat_id, "fight")
        await audit(client, chat_id, "fight_completed", state["challenger"], state["target"], f"Scores {first}:{second}")
        if query:
            await query.message.edit_text(text)
            await query.answer("Fight complete")
        elif message:
            await message.reply_text(text)

    async def fight_callback(client, query):
        if not query.message:
            return
        try:
            await resolve_fight(client, query.message.chat.id, query.from_user.id, query=query)
        except Exception:
            log.exception("Fight callback failed")
            await query.answer("Could not resolve the fight.", show_alert=True)

    app.add_handler(MessageHandler(fight, filters.command("fight") & filters.group))
    app.add_handler(MessageHandler(accept_fight, filters.command("accept") & filters.group))
    app.add_handler(CallbackQueryHandler(fight_callback, filters.regex(r"^fight:")))
