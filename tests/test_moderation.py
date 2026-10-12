import unittest
from unittest.mock import AsyncMock, patch

from config import Settings
from services.moderation_service import warn_member
from database import warnings as warning_db
from database.warnings import active_count


TEST_SETTINGS = Settings(
    api_id=1, api_hash="test", bot_token="1:test", mongodb_uri="mongodb://localhost",
    mongodb_database="test", owner_ids=frozenset({9001}), log_level="INFO",
    session_name="test", warning_limit=3,
)


class WarningTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_active_warnings_trigger_one_ban(self):
        client = AsyncMock()
        client.ban_chat_member = AsyncMock()
        sequence = [(1, {}), (2, {}), (3, {})]
        with (
            patch("services.moderation_service.is_protected", new=AsyncMock(return_value=False)),
            patch("services.moderation_service.get_settings", new=AsyncMock(return_value={"warning_limit": 3, "warning_expiry_hours": 0})),
            patch("services.moderation_service.add_warning", new=AsyncMock(side_effect=sequence)),
            patch("services.moderation_service.audit", new=AsyncMock()),
            patch("services.moderation_service.clear_active_warnings", new=AsyncMock()) as clear,
        ):
            results = [
                await warn_member(client, -1001, 77, 88, "test", TEST_SETTINGS)
                for _ in range(3)
            ]
        self.assertEqual([count for count, _ in results], [1, 2, 3])
        self.assertEqual([banned for _, banned in results], [False, False, True])
        client.ban_chat_member.assert_awaited_once_with(-1001, 77)
        clear.assert_awaited_once_with(-1001, 77)

    def test_expired_warning_does_not_count_as_active(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        self.assertEqual(active_count({"active": [
            {"expires_at": now - timedelta(seconds=1)},
            {"expires_at": None},
            {"expires_at": now + timedelta(minutes=1)},
        ]}, now), 2)

    async def test_warning_insert_uses_single_atomic_update_pipeline(self):
        class FakeWarnings:
            def __init__(self):
                self.pipeline = None
                self.inserted = []

            async def find_one_and_update(self, query, update, **kwargs):
                self.pipeline = update
                return {"chat_id": -1001, "user_id": 77, "active": [{"expires_at": None}], "total": 1}

            async def insert_one(self, event):
                self.inserted.append(event)

        fake = FakeWarnings()
        with patch("database.warnings.collection", return_value=fake):
            count, doc = await warning_db.add_warning(-1001, 77, 88, "reason")
        self.assertEqual(count, 1)
        self.assertIsInstance(fake.pipeline, list)
        self.assertEqual(len(fake.pipeline), 1)
        self.assertEqual(fake.inserted[0]["chat_id"], -1001)
        self.assertEqual(fake.inserted[0]["by"], 88)


if __name__ == "__main__":
    unittest.main()
