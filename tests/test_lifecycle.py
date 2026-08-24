"""Agent lifecycle and audit-trail tests.

Pins the state machine added in the best-in-class pass: guarded transitions
(approve/pause/resume/stop), the per-action audit trail with actor identity,
the agent detail endpoint, and paginated channel messages.
"""

import asyncio
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient


class LifecycleTestCase(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "test.db"
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    def _deploy(self, name="Lifecycle Copilot"):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        r = self.client.post("/api/agents/deploy", headers={"X-Acting-User": "alice"}, json={
            "process_id": process["id"],
            "name": name,
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]},
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class TestGuardedTransitions(LifecycleTestCase):
    def test_full_lifecycle_with_resume_and_stop(self):
        agent = self._deploy()
        aid = agent["id"]

        pause_before_running = self.client.post(f"/api/agents/{aid}/pause")
        self.assertEqual(pause_before_running.status_code, 409)

        resume_before_pause = self.client.post(f"/api/agents/{aid}/resume")
        self.assertEqual(resume_before_pause.status_code, 409)

        approved = self.client.post(f"/api/agents/{aid}/approve",
                                    headers={"X-Acting-User": "bob"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "running")

        paused = self.client.post(f"/api/agents/{aid}/pause")
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["status"], "paused")

        resumed = self.client.post(f"/api/agents/{aid}/resume")
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], "running")

        stopped = self.client.post(f"/api/agents/{aid}/stop")
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(stopped.json()["status"], "stopped")

        # Stopped is terminal.
        self.assertEqual(self.client.post(f"/api/agents/{aid}/resume").status_code, 409)
        self.assertEqual(self.client.post(f"/api/agents/{aid}/stop").status_code, 409)

    def test_double_approve_is_409_not_silent(self):
        agent = self._deploy()
        first = self.client.post(f"/api/agents/{agent['id']}/approve")
        second = self.client.post(f"/api/agents/{agent['id']}/approve")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)


class TestAuditTrail(LifecycleTestCase):
    def test_actions_record_actor_and_timestamp(self):
        agent = self._deploy()
        aid = agent["id"]
        self.client.post(f"/api/agents/{aid}/approve", headers={"X-Acting-User": "bob"})
        self.client.post(f"/api/agents/{aid}/pause", headers={"X-Acting-User": "carol"})

        detail = self.client.get(f"/api/agents/{aid}").json()
        trail = detail["metrics"]["audit"]
        actions = [entry["action"] for entry in trail]
        actors = [entry["actor"] for entry in trail]
        self.assertIn("deploy", actions)
        self.assertIn("approve", actions)
        self.assertIn("pause", actions)
        self.assertEqual([a for a in actors if a], ["alice", "bob", "carol"])
        for entry in trail:
            self.assertIn("at", entry)
        self.assertEqual(detail["metrics"]["approved_by"], "bob")

    def test_missing_actor_is_recorded_as_anonymous(self):
        agent = self._deploy()
        self.client.post(f"/api/agents/{agent['id']}/approve")  # no header
        detail = self.client.get(f"/api/agents/{agent['id']}").json()
        approve_entry = next(e for e in detail["metrics"]["audit"]
                             if e["action"] == "approve")
        self.assertEqual(approve_entry["actor"], "anonymous")


class TestMessagePagination(LifecycleTestCase):
    def test_messages_endpoint_paginates_and_404s(self):
        channels = self.client.get("/api/channels/").json()
        cid = channels[0]["id"]
        page1 = self.client.get(f"/api/channels/{cid}/messages",
                                params={"limit": 5, "offset": 0}).json()
        page2 = self.client.get(f"/api/channels/{cid}/messages",
                                params={"limit": 5, "offset": 5}).json()
        self.assertGreater(len(page1), 0)
        ids1 = {m["id"] for m in page1}
        ids2 = {m["id"] for m in page2}
        self.assertFalse(ids1 & ids2, "pages overlap")
        timestamps = [m["timestamp"] for m in page1]
        self.assertEqual(timestamps, sorted(timestamps))

        missing = self.client.get("/api/channels/nope/messages")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
