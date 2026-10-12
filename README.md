# ᴀʀᴇꜱxᴄʜᴀᴛʙᴏᴛ

An async Telegram group moderation and entertainment bot built with **Python 3.11+**, **Pyrogram 2.0.106**, and **PyMongo's asynchronous client**. It stores group configuration and game state in MongoDB Atlas and is designed to run as a single Railway worker.

## Features

- Per-group settings dashboard and command controls, with live Telegram admin checks on sensitive actions and callbacks.
- Warnings with persistent per-group history, expiry, and an atomic active-warning counter. Three active warnings trigger an automatic ban by default.
- Mute/unmute, ban/unban, kick and up-to-100-message purge; protected global owners, group creators and admins cannot be moderated.
- Hindi/Hinglish/English starter abuse terms, group-customizable word lists, flood/repeat detection and link allow-lists.
- Owner-only lockdown with explicit `/lockdown confirm`, saved group-default permissions, an audit entry, and `/unlock` restoration.
- Welcome and goodbye templates, optional stored photo, button rows, rules links and service-message cleanup.
- Persistent XP, aura, levels, message rankings, daily rewards/streaks and per-group statistics.
- Turn-based fights, persistent quiz/word game rounds, and cooldown-limited mini-games.
- Optional per-group audit log channel and MongoDB activity records.

MongoDB uses `AsyncMongoClient` from PyMongo 4.13.2. Motor was not selected because it is deprecated; the supported async driver is pinned directly. Pyrogram 2.0.106 supports Python 3.11+ and is pinned to keep Telegram behavior reproducible.

## Local setup

1. Create a Telegram bot with **@BotFather** and copy its bot token.
2. Get `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
3. Create a MongoDB Atlas database user and database. Add the deployment network to the Atlas IP access list; use the Atlas SRV URI (`mongodb+srv://...`) and URL-encode special characters in the database password.
4. Copy `.env.example` to `.env`; replace placeholders locally. Do not send tokens or database credentials in chat, and never commit `.env`.
5. Install dependencies and run:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

`main.py` validates required variables, pings MongoDB, creates indexes, registers all handlers, then starts the bot. It closes the Telegram client, scheduled tasks and database client on shutdown.

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `API_ID` | Yes | Telegram application ID from my.telegram.org |
| `API_HASH` | Yes | Telegram application hash |
| `BOT_TOKEN` | Yes | BotFather token |
| `MONGODB_URI` | Yes | Atlas `mongodb+srv://` or MongoDB URI |
| `MONGODB_DATABASE` | No | Database name; defaults to `ares_chatbot` |
| `OWNER_IDS` | Yes | Comma-separated trusted Telegram numeric user IDs |
| `DEFAULT_WARNING_LIMIT` | No | New-group warning threshold; defaults to `3` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `SESSION_NAME` | No | Pyrogram session name; defaults to `aresxchatbot` |

The bot does not need credentials in source code or in GitHub. For production, add each variable through Railway's **Variables** UI. Configure the same secrets locally through your shell or an ignored `.env` file.

## Add it to a group

1. Add the bot and promote it to administrator.
2. Grant **Delete messages**, **Ban users**, and **Restrict members** for moderation; **Manage chat**/permission editing for lockdown; and permission to send messages/media for welcome and logs. Only grant the permissions your group needs.
3. If the bot is not an administrator, disable BotFather's privacy mode for message-based abuse, repeat and link filtering. Telegram administrators receive regular group messages under Telegram's bot behavior.
4. Use `/settings` in the group. The bot reads actual Telegram membership before admin commands and each settings callback.
5. To configure a log channel, add the bot there with permission to post and set `/setlog <numeric_channel_id>` in the group.

Group-owner operations (`/lockdown`, `/unlock`) require either the live Telegram group creator account or a numeric ID listed in `OWNER_IDS`. A group lockdown changes the default member permissions; administrators can continue coordinating because Telegram administrators bypass those member defaults. The saved permissions are restored by `/unlock`.

## Commands

**Moderation (group admins):**
`/warn`, `/warnings`, `/mute [duration]`, `/unmute`, `/ban`, `/unban`, `/kick`, `/purge [1–100]`.
Reply to a member or use a numeric ID / username where applicable. Durations accept `30s`, `15m`, `2h` or `3d`.

**Group configuration (admins):**
`/settings`, `/groupconfig`, `/setwarninglimit 3`, `/setwarningexpiry 24`, `/setmuteduration 30`, `/setlog <channel_id|off>`, `/filters abuse|flood|links on|off`, `/abusewords add|remove|list|reset [term]`, `/allowlink <URL>` or `/allowlink remove <URL>`, `/xp on|off`, `/setxpreward 5`, `/setgamecooldown 10`, `/servicecleanup join|leave on|off`.

Welcome and goodbye: `/setwelcome <text>`, `/welcome on|off`, `/setwelcomepic` (reply to a photo), `/clearwelcomepic`, `/addwelcomebutton Label | https://example.com`, `/clearwelcomebuttons`, `/setrules <URL>`, `/setgoodbye <text>`, `/goodbye on|off`. Templates support `{first_name}`, `{username}`, `{chat_title}`, and `{members_count}`. A rules URL appears as a welcome button. Custom buttons are limited to eight per group.

**Owner emergency controls:** `/lockdown` presents a confirmation step; `/lockdown confirm` applies it. `/unlock` restores the saved permissions. There is intentionally no mass-ban command.

**Games and stats:** `/fight`, `/accept`, `/quiz`, `/wordgame`, `/answer <text>`, `/rps rock|paper|scissors`, `/roll [maximum]`, `/coinflip`, `/8ball <question>`, `/truth`, `/dare`, `/ship`, `/lovepair`, `/rank`, `/aura`, `/leaderboard`, `/topmessages`, `/mystats`, `/groupstats`, `/daily`, `/help`.

Love-pair and ship scores are entertainment only, not real compatibility assessments. XP is limited by per-group message/game cooldowns; game state is stored in MongoDB so active rounds survive process restarts.

## Tests

Run the included unit suite without Telegram or MongoDB credentials:

```bash
python -m unittest discover -v
python -m compileall -q config.py main.py database handlers keyboards services utils
```

Unit tests cover live admin permission checks, the third-warning ban threshold, group-setting isolation, symmetric fight scoring, level thresholds, and that every command shown in `/help` is registered. They do not replace a live Telegram/MongoDB integration test.

## Railway deployment

1. Create a Railway service connected to this repository.
2. Add the required variables from the environment table via Railway's Variables UI. Keep tokens and the Atlas URI out of chat, commits, and build logs.
3. Deploy as a **worker**. `Procfile` and `railway.json` both use `python main.py`; `requirements.txt` pins the runtime packages.
4. Verify Railway logs show MongoDB connected and the bot started. Then add the bot to a test group and check `/help`, `/settings`, and one moderation action before enabling filters in a production group.

## Safety and operational notes

- The checked-in `.env.example` contains placeholders only; `.gitignore` excludes `.env` and Pyrogram session files.
- Warning-counter changes use a MongoDB update pipeline; warning event history is stored separately and retained.
- Permission checks fail closed if Telegram membership lookup fails. Telegram/Bot API errors are handled without logging credentials.
- Flood-wait errors are logged and cooled down; Pyrogram's `sleep_threshold` handles shorter waits automatically.
- Repeated-message and flood windows are process-local; persistent XP, warning history, group settings, game rounds and activity records are in MongoDB.
- Lockdown saves the permission fields supported by this pinned Bot API client. If Telegram changes permission semantics or the bot loses admin rights during a lockdown, an owner may need to restore settings manually in Telegram.
- Add MongoDB backup/retention policies appropriate for your community; audit events and warning history contain group moderation data.
