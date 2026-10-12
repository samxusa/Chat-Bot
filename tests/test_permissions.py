import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyrogram.enums import ChatMemberStatus

from config import Settings
from services.permissions import can_manage, is_chat_admin, is_privileged_status, is_protected


TEST_SETTINGS = Settings(
    api_id=1, api_hash="test", bot_token="1:test", mongodb_uri="mongodb://localhost",
    mongodb_database="test", owner_ids=frozenset({9001}), log_level="INFO",
    session_name="test", warning_limit=3,
)


class PermissionsTests(unittest.IsolatedAsyncioTestCase):
    def test_admin_status_recognition(self):
        self.assertTrue(is_privileged_status(ChatMemberStatus.OWNER))
        self.assertTrue(is_privileged_status(ChatMemberStatus.ADMINISTRATOR))
        self.assertFalse(is_privileged_status(ChatMemberStatus.MEMBER))

    async def test_admin_and_owner_checks_use_live_membership(self):
        client = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR))
        )
        self.assertTrue(await is_chat_admin(client, -1001, 42))
        self.assertTrue(await can_manage(client, -1001, 42, TEST_SETTINGS))
        self.assertFalse(await can_manage(client, -1001, 42, TEST_SETTINGS, owner_only=True))
        self.assertTrue(await can_manage(client, -1001, 9001, TEST_SETTINGS, owner_only=True))
        self.assertTrue(await is_protected(client, -1001, 42, TEST_SETTINGS))

    async def test_failed_telegram_lookup_is_not_admin(self):
        client = SimpleNamespace(get_chat_member=AsyncMock(side_effect=RuntimeError("lookup failed")))
        self.assertFalse(await is_chat_admin(client, -1001, 42))


if __name__ == "__main__":
    unittest.main()
