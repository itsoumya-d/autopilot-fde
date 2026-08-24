"""API guard-branch tests: 404 surfaces, deploy refusals, audit repair.

Complements test_api.py by pinning every error path the happy-path suite
skips, so the coverage gate can sit at 100% honestly.
"""

import asyncio
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient


class GuardApiTestCase(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "guards.db"
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

    def _first_process_and_score(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        return process, score

    def _deploy(self, name="Guard Copilot", config=None):
        process, score = self._first_process_and_score()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        payload = {"mode": "draft", "approval_required": True,
                   "enabled_steps": score["eligible_steps"][:1]}
        if config:
            payload.update(config)
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": name, "config": payload})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()


class TestDeployRefusals(GuardApiTestCase):
    def test_unknown_process_is_404(self):
        response = self.client.post("/api/agents/deploy", json={
            "process_id": "proc-missing", "name": "Ghost Copilot",
            "config": {"mode": "draft", "approval_required": True}})
        self.assertEqual(response.status_code, 404)

    def test_approval_disabled_is_refused_independently(self):
        process, _ = self._first_process_and_score()
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Unguarded Copilot",
            "config": {"mode": "draft", "approval_required": False}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("approval gate", response.json()["detail"])

    def test_ineligible_steps_are_refused(self):
        process, _ = self._first_process_and_score()
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Overreach Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": ["Definitely Not A Step"]}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("not eligible", response.json()["detail"])

    def test_empty_enabled_steps_defaults_to_first_eligible(self):
        process, score = self._first_process_and_score()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps")
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Default Steps Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": []}})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["config"]["enabled_steps"],
                         score["eligible_steps"][:1])

    def test_compile_failure_returns_500(self):
        from backend.api import agents as agents_mod

        broken = SimpleNamespace(python_code="def oops(:\n    pass",
                                 process_id="p", agent_name="x", tools=[],
                                 entrypoint="", langgraph_spec={})
        with mock.patch.object(agents_mod._factory, "generate_langgraph_code",
                               return_value=broken):
            process, _ = self._first_process_and_score()
            response = self.client.post("/api/agents/deploy", json={
                "process_id": process["id"], "name": "Broken Build Copilot",
                "config": {"mode": "draft", "approval_required": True}})
        self.assertEqual(response.status_code, 500)
        self.assertIn("failed validation", response.json()["detail"])


class TestAgentEndpoint404s(GuardApiTestCase):
    def test_list_agents_endpoint_returns_collection(self):
        listed = self.client.get("/api/agents/")
        self.assertEqual(listed.status_code, 200)
        self.assertIsInstance(listed.json(), list)

    def _hit_all_routes_for_missing_agent(self):
        return [
            self.client.get("/api/agents/agent-missing").status_code,
            self.client.post("/api/agents/agent-missing/approve").status_code,
            self.client.post("/api/agents/agent-missing/pause").status_code,
            self.client.post("/api/agents/agent-missing/resume").status_code,
            self.client.post("/api/agents/agent-missing/stop").status_code,
            self.client.post("/api/agents/agent-missing/draft",
                             json={"source_text": "some source text"}).status_code,
            self.client.delete("/api/agents/agent-missing").status_code,
        ]

    def test_every_route_404s_for_unknown_agent(self):
        for status_code in self._hit_all_routes_for_missing_agent():
            self.assertEqual(status_code, 404)

    def test_undeploy_success_removes_branch(self):
        agent = self._deploy()
        removed = self.client.delete(f"/api/agents/{agent['id']}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.client.get(f"/api/agents/{agent['id']}").status_code, 404)

    def test_corrupt_audit_trail_is_repaired_on_next_action(self):
        agent = self._deploy(name="Corrupt Audit Copilot")
        raw = asyncio.run(self._db.get_agent(agent["id"]))
        raw.metrics["audit"] = "corrupted-by-bug"
        asyncio.run(self._db.save_agent(raw))

        approved = self.client.post(f"/api/agents/{raw.id}/approve")
        self.assertEqual(approved.status_code, 200)
        repaired = asyncio.run(self._db.get_agent(raw.id))
        self.assertIsInstance(repaired.metrics["audit"], list)
        self.assertEqual([e["action"] for e in repaired.metrics["audit"]],
                         ["approve"])


class TestProcessAndScoreReads404(GuardApiTestCase):
    def test_process_detail_and_404(self):
        process = self.client.get("/api/processes/").json()[0]
        found = self.client.get(f"/api/processes/{process['id']}")
        self.assertEqual(found.status_code, 200)
        missing = self.client.get("/api/processes/proc-missing")
        self.assertEqual(missing.status_code, 404)

    def test_recommendations_endpoint_lists_waves(self):
        response = self.client.get("/api/scores/recommendations")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreater(len(body), 0)
        self.assertIn("wave", body[0])

    def test_score_detail_404(self):
        self.assertEqual(
            self.client.get("/api/scores/proc-missing").status_code, 404)

    def test_simulate_unknown_process_404(self):
        self.assertEqual(
            self.client.get("/api/scores/simulate/proc-missing",
                            params={"runs": 100}).status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
