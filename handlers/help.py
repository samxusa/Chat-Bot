from pyrogram import filters
from pyrogram.handlers import MessageHandler

from config import Settings


HELP_TEXT = """<b>ᴀʀᴇꜱxᴄʜᴀᴛʙᴏᴛ — commands</b>

<b>Moderation (group admins)</b>
/warn · /warnings · /mute [duration] · /unmute
/ban · /unban · /kick · /purge [1–100]
/lockdown → confirmation required; /unlock (group owner only)

<b>Group setup (admins)</b>
/settings · /setwarninglimit 3 · /setwarningexpiry 0 · /setmuteduration 30
/setlog &lt;channel_id|off&gt;
/setwelcome &lt;text&gt; · /welcome on|off · /setwelcomepic (reply to photo)
/setgoodbye &lt;text&gt; · /goodbye on|off · /setrules &lt;URL&gt;
/addwelcomebutton Label | URL · /clearwelcomebuttons
/allowlink &lt;URL&gt; · /allowlink remove &lt;URL&gt;
/filters abuse|flood|links on|off · /abusewords add|remove|list|reset [term]
/servicecleanup join|leave on|off · /setxpreward 5 · /setgamecooldown 10 · /xp on|off
Welcome tokens: {first_name}, {username}, {chat_title}, {members_count}

<b>Games and stats</b>
/fight (reply or @username) · /accept · /quiz · /wordgame · /answer &lt;text&gt;
/rps rock|paper|scissors · /roll [max] · /coinflip · /8ball &lt;question&gt;
/truth · /dare · /ship (reply or @username) · /lovepair
/rank · /aura · /leaderboard · /topmessages · /mystats · /groupstats · /daily

Games are for fun; love pairing is not a real compatibility assessment.
Bot needs admin rights for moderation, deleting messages, welcome cleanup and lockdown."""


def register(app, settings: Settings) -> None:
    async def help_command(client, message):
        await message.reply_text(HELP_TEXT, disable_web_page_preview=True)

    app.add_handler(MessageHandler(help_command, filters.command("help")))
