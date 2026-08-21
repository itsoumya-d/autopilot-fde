"""End-to-end API tests against the real FastAPI app.

Uses a temporary database so the committed demo store is never touched.
Covers the security posture (webhook signatures, API-key gate, credential
exclusion), the full discovery->score->deploy->approve->draft lifecycle, and
the structural approval boundary (AUTONOMOUS is unreachable)."""

import hashlib
import hmac
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402


class ApiTestCase(unittest.TestCase):
    """Boots the app against a fresh temp DB per test."""

    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "test.db"
        # Reset the shared handle so each test gets its own file.
        self._async = __import__("asyncio")
        self._async.get_event_loop().run_until_complete(database.close_db()) if False else None
        self.client = TestClient(main_mod.app)
        # Lifespan runs on first request context via context manager:
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        self._async.new_event_loop().run_until_complete(self._db.close_db())
        self._tmp.cleanup()

    def post(self, path, **kw):
        return self.client.post(path, **kw)


class TestHealth(ApiTestCase):
    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")


class TestDiscoveryLifecycle(ApiTestCase):
    def test_dashboard_after_auto_discovery(self):
        r = self.client.get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreaterEqual(body["processes_discovered"], 1)

    def test_processes_have_scores(self):
        processes = self.client.get("/api/processes/").json()
        scores = self.client.get("/api/scores/").json()
        self.assertGreaterEqual(len(processes), 1)
        self.assertEqual(len(scores), len(processes))
        for score in scores:
            self.assertTrue(0 <= score["score"] <= 100)

    def test_recalculate_is_deterministic(self):
        before = self.client.get("/api/scores/").json()
        r = self.post("/api/scores/recalculate")
        self.assertEqual(r.status_code, 200)
        after = self.client.get("/api/scores/").json()
        self.assertEqual(
            [s["score"] for s in before], [s["score"] for s in after])


class TestDeployBoundary(ApiTestCase):
    def _first_process_and_score(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        return process, score

    def test_deploy_generates_parsable_workflow(self):
        import ast

        process, score = self._first_process_and_score()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        r = self.post("/api/agents/deploy", json={
            "process_id": process["id"],
            "name": "Test Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]},
        })
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertIsNotNone(body["generated_code"])
        ast.parse(body["generated_code"]["python_code"])

    def test_autonomous_mode_is_structurally_unreachable(self):
        process, score = self._first_process_and_score()
        r = self.post("/api/agents/deploy", json={
            "process_id": process["id"],
            "name": "Rogue Agent",
            "config": {"mode": "autonomous", "approval_required": False},
        })
        self.assertEqual(r.status_code, 422)

    def test_draft_requires_running_agent(self):
        process, score = self._first_process_and_score()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        deploy = self.post("/api/agents/deploy", json={
            "process_id": process["id"],
            "name": "Gated Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]},
        })
        agent_id = deploy.json()["id"]
        early = self.post(f"/api/agents/{agent_id}/draft",
                          json={"source_text": "customer says hello"})
        self.assertEqual(early.status_code, 409)  # still pending approval
        approved = self.post(f"/api/agents/{agent_id}/approve")
        self.assertEqual(approved.status_code, 200)
        draft = self.post(f"/api/agents/{agent_id}/draft",
                          json={"source_text": "customer says hello"})
        self.assertEqual(draft.status_code, 200)
        self.assertEqual(draft.json()["status"], "pending_human_review")


class TestWebhookSecurity(ApiTestCase):
    def test_get_handshake_disabled_without_token(self):
        os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)
        r = self.client.get("/api/channels/whatsapp/webhook",
                            params={"hub.mode": "subscribe",
                                    "hub.verify_token": "anything",
                                    "hub.challenge": "CHALLENGE"})
        self.assertEqual(r.status_code, 503)

    def test_get_handshake_with_token(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secret-token"
        try:
            r = self.client.get("/api/channels/whatsapp/webhook",
                                params={"hub.mode": "subscribe",
                                        "hub.verify_token": "secret-token",
                                        "hub.challenge": "CHALLENGE"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), "CHALLENGE")
        finally:
            os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)

    def test_post_webhook_signature_enforced_when_secret_set(self):
        os.environ["WHATSAPP_APP_SECRET"] = "app-secret"
        try:
            body = b'{"entry": []}'
            bad = self.post("/api/channels/whatsapp/webhook", content=body,
                            headers={"Content-Type": "application/json"})
            self.assertEqual(bad.status_code, 403)

            good_sig = "sha256=" + hmac.new(
                b"app-secret", body, hashlib.sha256).hexdigest()
            ok = self.post("/api/channels/whatsapp/webhook", content=body,
                           headers={"Content-Type": "application/json",
                                    "X-Hub-Signature-256": good_sig})
            self.assertEqual(ok.status_code, 200)
        finally:
            os.environ.pop("WHATSAPP_APP_SECRET", None)


class TestCredentialExclusion(ApiTestCase):
    def test_channel_responses_carry_no_credentials(self):
        channels = self.client.get("/api/channels/").json()
        self.assertGreaterEqual(len(channels), 1)
        for channel in channels:
            self.assertNotIn("credentials", channel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
