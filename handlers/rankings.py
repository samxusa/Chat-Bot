from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings
from database.statistics import group_summary
from database.groups import get_settings
from database.users import get_user, top_users
from services.xp_service import daily_reward
from utils.formatters import display_name, escape

log = logging.getLogger(__name__)


def register(app, settings: Settings) -> None:
    async def rank(client, message):
        try:
            user = message.from_user
            if not user and message.reply_to_message:
                user = message.reply_to_message.from_user
            if not user:
                await message.reply_text("Use /rank in a group.")
                return
            stats = await get_user(message.chat.id, user.id)
            better = await __import__("database.mongo", fromlist=["collection"]).collection("users").count_documents(
                {"chat_id": message.chat.id, "xp": {"$gt": int(stats.get("xp", 0))}}
            )
            await message.reply_text(
                f"🏅 {escape(display_name(user))} · rank #{better + 1}\n"
                f"Level {stats.get('level', 1)} · {stats.get('xp', 0)} XP · {stats.get('aura', 0)} aura"
            )
        except Exception:
            log.exception("Rank command failed")
            await message.reply_text("Could not load your rank.")

    async def leaderboard(client, message):
        try:
            rows = await top_users(message.chat.id, "xp", 10)
            if not rows:
                await message.reply_text("No activity has been recorded yet.")
                return
            lines = ["🏆 <b>XP leaderboard</b>"]
            for place, row in enumerate(rows, 1):
                name = row.get("first_name") or (f"@{row['username']}" if row.get("username") else str(row["user_id"]))
                lines.append(f"{place}. {escape(name)} — {row.get('xp', 0)} XP · level {row.get('level', 1)}")
            await message.reply_text("\n".join(lines))
        except Exception:
            log.exception("Leaderboard failed")
            await message.reply_text("Could not load the leaderboard.")

    async def topmessages(client, message):
        try:
            rows = await top_users(message.chat.id, "message_count", 10)
            lines = ["💬 <b>Most messages recorded</b>"]
            for place, row in enumerate(rows, 1):
                name = row.get("first_name") or str(row["user_id"])
                lines.append(f"{place}. {escape(name)} — {row.get('message_count', 0)}")
            await message.reply_text("\n".join(lines) if rows else "No message stats yet.")
        except Exception:
            log.exception("Top messages failed")
            await message.reply_text("Could not load message rankings.")

    async def mystats(client, message):
        if not message.from_user:
            return
        row = await get_user(message.chat.id, message.from_user.id)
        await message.reply_text(
            f"📊 <b>Your stats</b>\nLevel: {row.get('level', 1)}\nXP: {row.get('xp', 0)}\n"
            f"Aura: {row.get('aura', 0)}\nMessages: {row.get('message_count', 0)}\n"
            f"Win/loss: {row.get('wins', 0)}/{row.get('losses', 0)}\nDaily streak: {row.get('daily_streak', 0)}\n"
            f"Achievements: {', '.join(row.get('achievements', [])) or 'none yet'}"
        )

    async def groupstats(client, message):
        stats = await group_summary(message.chat.id)
        await message.reply_text(
            f"📈 <b>Group activity</b>\nTracked members: {stats['members_tracked']}\n"
            f"Messages: {stats['messages']}\nCombined XP: {stats['xp']}\nActive today: {stats['active_today']}"
        )

    async def daily(client, message):
        if not message.from_user:
            return
        try:
            config = await get_settings(message.chat.id)
            if not config["xp_enabled"]:
                await message.reply_text("XP rewards are disabled for this group.")
                return
            ok, reward, streak = await daily_reward(message.chat.id, message.from_user.id)
            await message.reply_text(
                f"🎁 Daily reward: +{reward} XP · {streak}-day streak!" if ok
                else f"You already claimed today's reward. Current streak: {streak} day(s)."
            )
        except Exception:
            log.exception("Daily reward failed")
            await message.reply_text("Could not claim the daily reward.")

    commands = {
        "rank": rank, "leaderboard": leaderboard, "topmessages": topmessages,
        "mystats": mystats, "groupstats": groupstats, "daily": daily,
    }
    for name, callback in commands.items():
        app.add_handler(MessageHandler(callback, filters.command(name) & filters.group))
