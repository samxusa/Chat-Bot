import re
import unittest

from pyrogram import filters

Filter = filters.Filter
CommandFilter = type(filters.command("registration_probe"))

from config import Settings
from handlers import (
    abuse_filter, activity, admin, anti_spam, aura, chatfight, goodbye, help,
    minigames, moderation, quiz, rankings, settings as group_settings,
    social, welcome, wordgame,
)
from handlers.help import HELP_TEXT


class FakeApp:
    def __init__(self):
        self.handlers = []

    def add_handler(self, handler, group=0):
        self.handlers.append((handler, group))


def command_names(filter_obj):
    if type(filter_obj).__name__ == "CommandFilter":
        return set(filter_obj.commands)
    found = set()
    if isinstance(filter_obj, Filter):
        for value in vars(filter_obj).values():
            if isinstance(value, Filter):
                found.update(command_names(value))
    return found


class HandlerRegistrationTests(unittest.TestCase):
    def test_every_command_in_help_is_registered(self):
        settings = Settings(
            api_id=1, api_hash="test", bot_token="1:test", mongodb_uri="mongodb://localhost",
            mongodb_database="test", owner_ids=frozenset({9001}), log_level="INFO",
            session_name="test", warning_limit=3,
        )
        app = FakeApp()
        modules = (
            help, moderation, admin, group_settings, welcome, goodbye, abuse_filter, aura,
            anti_spam, chatfight, quiz, wordgame, minigames, social, rankings, activity,
        )
        for module in modules:
            module.register(app, settings)
        registered = set()
        for handler, _ in app.handlers:
            registered.update(command_names(handler.filters))
        plain_help = re.sub(r"</?[a-z]+>", "", HELP_TEXT.lower())
        advertised = set(re.findall(r"/([a-z0-9_]+)", plain_help))
        missing = sorted(advertised - registered)
        self.assertEqual(missing, [], f"Help lists unregistered commands: {missing}")
        self.assertGreaterEqual(len(app.handlers), 40)


if __name__ == "__main__":
    unittest.main()
