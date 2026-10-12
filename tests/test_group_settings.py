import copy
import unittest
from unittest.mock import patch

from database import groups


class FakeGroupsCollection:
    def __init__(self):
        self.rows = {}

    async def find_one_and_update(self, query, update, **kwargs):
        key = query["_id"]
        is_new = key not in self.rows
        self.rows.setdefault(key, {"_id": key})
        if is_new:
            self.rows[key].update(update.get("$setOnInsert", {}))
        return copy.deepcopy(self.rows[key])

    async def update_one(self, query, update, **kwargs):
        key = query["_id"]
        is_new = key not in self.rows
        self.rows.setdefault(key, {"_id": key})
        if is_new:
            self.rows[key].update(update.get("$setOnInsert", {}))
        self.rows[key].update(update.get("$set", {}))


class GroupSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_settings_are_isolated(self):
        fake = FakeGroupsCollection()
        with patch("database.groups.collection", return_value=fake):
            await groups.set_setting(-1001, "abuse_filter", False)
            await groups.set_setting(-1002, "abuse_filter", True)
            await groups.set_setting(-1001, "warning_limit", 5)
            first = await groups.get_settings(-1001)
            second = await groups.get_settings(-1002)
        self.assertFalse(first["abuse_filter"])
        self.assertEqual(first["warning_limit"], 5)
        self.assertTrue(second["abuse_filter"])
        self.assertEqual(second["warning_limit"], 3)


if __name__ == "__main__":
    unittest.main()
