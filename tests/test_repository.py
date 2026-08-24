"""Repository-layer tests for database helpers not exercised via HTTP paths."""

import asyncio
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend import database  # noqa: E402
from backend.demo_data import demo_channel, demo_messages  # noqa: E402
from backend.models.schema import AgentBranch, AgentStatus, DeploymentConfig  # noqa: E402


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "repo.db"

    def tearDown(self):
        asyncio.run(database.close_db())
        self._tmp.cleanup()


class TestMessageQueries(RepositoryTestCase):
    def seed(self):
        asyncio.run(database.init_db())
        asyncio.run(database.upsert_channel(demo_channel()))
        asyncio.run(database.create_messages(demo_messages()))

    def test_create_messages_with_empty_batch_is_noop(self):
        asyncio.run(database.init_db())
        self.assertIsNone(asyncio.run(database.create_messages([])))
        self.assertEqual(asyncio.run(database.count_messages()), 0)

    def test_count_messages_filters_by_channel(self):
        self.seed()
        total = asyncio.run(database.count_messages())
        scoped = asyncio.run(database.count_messages(demo_channel().id))
        other = asyncio.run(database.count_messages("channel:missing"))
        self.assertEqual(total, scoped)
        self.assertEqual(other, 0)
        self.assertGreater(total, 0)

    def test_latest_message_timestamp_hit_and_miss(self):
        self.seed()
        latest = asyncio.run(database.latest_message_timestamp(demo_channel().id))
        self.assertIsInstance(latest, datetime)
        missing = asyncio.run(database.latest_message_timestamp("channel:missing"))
        self.assertIsNone(missing)


class TestAgentPersistence(RepositoryTestCase):
    def agent(self, agent_id="agent-repo1"):
        return AgentBranch(
            id=agent_id, process_id="proc-x", name="Repo Copilot",
            status=AgentStatus.PENDING_APPROVAL, config=DeploymentConfig(),
        )

    def test_save_agent_missing_row_raises_keyerror(self):
        asyncio.run(database.init_db())
        with self.assertRaises(KeyError):
            asyncio.run(database.save_agent(self.agent()))

    def test_delete_agent_reports_presence(self):
        asyncio.run(database.init_db())
        asyncio.run(database.create_agent(self.agent()))
        self.assertTrue(asyncio.run(database.delete_agent("agent-repo1")))
        self.assertFalse(asyncio.run(database.delete_agent("agent-repo1")))
        self.assertIsNone(asyncio.run(database.get_agent("agent-repo1")))

    def test_get_channel_found_and_missing(self):
        asyncio.run(database.init_db())
        asyncio.run(database.upsert_channel(demo_channel()))
        found = asyncio.run(database.get_channel(demo_channel().id))
        self.assertIsNotNone(found)
        self.assertEqual(found.id, demo_channel().id)
        self.assertIsNone(asyncio.run(database.get_channel("nope")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
