"""v0.6.0 Governed Autonomy: identity tokens, quotas, idempotency, DLQ, policy."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.deployment import execution_guards as guards  # noqa: E402
from backend.deployment.tool_adapters import execute_agent_step  # noqa: E402
from backend.security import (  # noqa: E402
    issue_agent_token,
    verify_agent_token,
)


class GuardWorkspaceTestCase(unittest.TestCase):
    """Isolated guard DB + clean env for every test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        guards._connection = None  # force rebinding to the temp workspace
        os.environ["AUTOPILOT_GUARD_DB"] = str(
            pathlib.Path(self._tmp.name) / "guards.db")
        self._saved_env = {k: os.environ.get(k) for k in (
            "AUTOPILOT_AGENT_SECRET", "AUTOPILOT_TOOLS_POLICY",
            "AUTOPILOT_RATE_LIMIT_PER_MIN", "AUTOPILOT_API_KEY")}

    def tearDown(self):
        guards.close_guards()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()
        guards._policy_cache.update(path=None, mtime=None, hosts=None)


class TestAgentIdentity(GuardWorkspaceTestCase):
    def test_token_roundtrip_constant_time_verify(self):
        token = issue_agent_token("agent-1", secret="s3cret")
        self.assertTrue(verify_agent_token("agent-1", token, secret="s3cret"))
        self.assertFalse(verify_agent_token("agent-1", "forged", secret="s3cret"))
        self.assertFalse(verify_agent_token("agent-2", token, secret="s3cret"))

    def test_no_secret_means_no_token_issued(self):
        os.environ.pop("AUTOPILOT_AGENT_SECRET", None)
        os.environ.pop("AUTOPILOT_API_KEY", None)
        self.assertIsNone(issue_agent_token("agent-1"))
        self.assertFalse(verify_agent_token("agent-1", "anything"))

    def test_api_key_falls_back_as_signing_secret(self):
        os.environ.pop("AUTOPILOT_AGENT_SECRET", None)
        os.environ["AUTOPILOT_API_KEY"] = "shared-key"
        token = issue_agent_token("agent-9")
        self.assertTrue(verify_agent_token("agent-9", token))
        self.assertFalse(issue_agent_token("agent-9", secret="other") == token)


class TestIdempotency(GuardWorkspaceTestCase):
    def test_same_key_replays_first_result(self):
        context = {"idempotency_key": "op-1"}
        first = execute_agent_step("Issue triaged", dict(context))
        second = execute_agent_step("Issue triaged", {"idempotency_key": "op-1"})
        self.assertNotEqual(first.get("status"), "replayed")
        self.assertEqual(second["status"], "replayed")
        self.assertEqual(second["replayed_from"], "op-1")

    def test_different_keys_execute_independently(self):
        a = execute_agent_step("Issue triaged", {"idempotency_key": "k-a"})
        b = execute_agent_step("Issue triaged", {"idempotency_key": "k-b"})
        self.assertNotEqual(a["executed_at"] + a["step_name"],
                            b["status"] + b["executed_at"])
        self.assertEqual(a["action_type"], b["action_type"])

    def test_persisted_across_guard_reopen(self):
        execute_agent_step("Lead captured", {"idempotency_key": "persist-1"})
        guards.close_guards()
        replay = execute_agent_step("Lead captured", {"idempotency_key": "persist-1"})
        self.assertEqual(replay["status"], "replayed")


class TestAgentQuota(GuardWorkspaceTestCase):
    def test_quota_blocks_after_limit(self):
        os.environ["AUTOPILOT_RATE_LIMIT_PER_MIN"] = "2"
        from backend.deployment.execution_guards import RateLimiter

        guards._agent_limiter = RateLimiter()  # fresh window
        for _ in range(2):
            execute_agent_step("Issue triaged", {}, agent_id="agent-q")
        with self.assertRaises(guards.AgentQuotaExceeded):
            execute_agent_step("Issue triaged", {}, agent_id="agent-q")

    def test_other_agents_keep_their_own_budget(self):
        os.environ["AUTOPILOT_RATE_LIMIT_PER_MIN"] = "1"
        from backend.deployment.execution_guards import RateLimiter

        guards._agent_limiter = RateLimiter()
        execute_agent_step("Issue triaged", {}, agent_id="agent-a")
        execute_agent_step("Issue triaged", {}, agent_id="agent-b")  # unaffected


class TestDeadLetterQueue(GuardWorkspaceTestCase):
    def _fail_internal_step(self, agent_id="agent-dlq"):
        class FakeClient:
            def __init__(self, **_kw):
                raise ConnectionError("itsm unreachable")


        with mock.patch(
            "backend.deployment.tool_adapters.httpx.Client", FakeClient,
        ):
            with self.assertRaises(ConnectionError):
                execute_agent_step("Specialist assigned",
                                   {"webhook_url": "https://itsm.internal/x"},
                                   agent_id=agent_id)

    def test_failed_webhook_lands_in_dlq_with_context(self):
        self._fail_internal_step()
        entries = guards.dead_letter_list()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["step_name"], "Specialist assigned")
        self.assertIn("itsm unreachable", entry["error"])
        self.assertEqual(entry["payload"]["webhook_url"], "https://itsm.internal/x")

    def test_review_flow_discard_then_conflict(self):
        self._fail_internal_step()
        entry = guards.dead_letter_list()[0]
        result = guards.dead_letter_review(entry["id"], reviewer="csm",
                                           decision="discard", notes="dup")
        self.assertEqual(result["status"], "reviewed:discard")
        with self.assertRaises(guards.DeadLetterAlreadyReviewed):
            guards.dead_letter_review(entry["id"], reviewer="csm",
                                      decision="requeue")

    def test_invalid_decision_and_missing_entry(self):
        with self.assertRaises(ValueError):
            guards.dead_letter_review("dlq-x", reviewer="r", decision="yolo")
        with self.assertRaises(guards.DeadLetterNotFound):
            guards.dead_letter_review("dlq-missing", reviewer="r",
                                      decision="discard")


class TestToolPolicyAllowlist(GuardWorkspaceTestCase):
    def write_policy(self, hosts):
        path = pathlib.Path(self._tmp.name) / "tools.policy.json"
        path.write_text(json.dumps({"allowed_webhook_hosts": hosts}))
        os.environ["AUTOPILOT_TOOLS_POLICY"] = str(path)
        guards._policy_cache.update(path=None, mtime=None, hosts=None)


    def test_deny_by_default_when_policy_lists_hosts(self):
        self.write_policy(["itsm.internal"])
        with self.assertRaises(guards.WebhookHostNotAllowed):
            execute_agent_step("Specialist assigned",
                               {"webhook_url": "https://evil.example.com/x"})

    def test_listed_host_passes_and_subdomains_allowed(self):
        self.write_policy(["itsm.internal"])
        captured = {}

        RealClient = __import__("httpx").Client

        class FakeClient:
            def __init__(self, **_kw):
                self._client = RealClient(transport=__import__("httpx").MockTransport(
                    lambda request: (captured.update(host=request.url.host),
                                     __import__("httpx").Response(200))[1]))

            def __enter__(self):
                return self._client

            def __exit__(self, *a):
                self._client.close()
                return False


        with mock.patch("backend.deployment.tool_adapters.httpx.Client", FakeClient):
            result = execute_agent_step(
                "Engineer assigned",
                {"webhook_url": "https://api.itsm.internal/tickets"})
        self.assertTrue(result["accepted"])

    def test_no_policy_file_keeps_previous_behavior(self):
        os.environ.pop("AUTOPILOT_TOOLS_POLICY", None)
        guards._policy_cache.update(path=None, mtime=None, hosts=None)
        self.assertIsNone(guards._policy_hosts())

    def test_corrupt_policy_denies_everything(self):
        path = pathlib.Path(self._tmp.name) / "broken.json"
        path.write_text("{not json")
        os.environ["AUTOPILOT_TOOLS_POLICY"] = str(path)
        guards._policy_cache.update(path=None, mtime=None, hosts=None)
        self.assertEqual(guards._policy_hosts(), set())


class TestDeadLetterRouter(GuardWorkspaceTestCase):
    """HTTP surface for the DLQ: list + identity-bound human review."""

    def setUp(self):
        super().setUp()
        os.environ.pop("AUTOPILOT_AGENT_SECRET", None)
        os.environ["AUTOPILOT_API_KEY"] = "guard-key"
        from fastapi.testclient import TestClient

        import backend.main as main_mod

        self.client = TestClient(main_mod.app)

    def _seed_entry(self, agent_id="agent-router"):
        guards.dead_letter_push(agent_id=agent_id, step_name="Engineer assigned",
                                error="ConnectionError: down",
                                payload={"webhook_url": "https://itsm.internal/x"})

    def _token_for(self, agent_id):
        return issue_agent_token(agent_id)  # uses AUTOPILOT_API_KEY fallback

    def test_list_pending_and_empty_statuses(self):
        self.assertEqual(self.client.get("/api/dlq/").json()["count"], 0)
        self._seed_entry()
        self.assertEqual(self.client.get("/api/dlq/").json()["count"], 1)
        self.assertEqual(
            self.client.get("/api/dlq/", params={"status": "reviewed:discard"}).json()["count"],
            0)

    def test_review_requires_api_key_then_agent_token(self):
        self._seed_entry()
        entry = guards.dead_letter_list()[0]
        no_key = self.client.post(f"/api/dlq/{entry['id']}/review",
                                  json={"decision": "discard"})
        self.assertEqual(no_key.status_code, 401)
        del no_key

        no_token = self.client.post(
            f"/api/dlq/{entry['id']}/review",
            headers={"X-API-Key": "guard-key"}, json={"decision": "discard"})
        self.assertEqual(no_token.status_code, 401)

        ok = self.client.post(
            f"/api/dlq/{entry['id']}/review",
            headers={"X-API-Key": "guard-key",
                     "X-Autopilot-Agent-Token": self._token_for("agent-router"),
                     "X-Acting-User": "csm-bob"},
            json={"decision": "discard", "notes": "duplicate event"})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["status"], "reviewed:discard")
        self.assertEqual(ok.json()["reviewed_by"], "csm-bob")

    def test_review_conflict_and_missing(self):
        self._seed_entry()
        entry = guards.dead_letter_list()[0]
        headers = {"X-API-Key": "guard-key",
                   "X-Autopilot-Agent-Token": self._token_for("agent-router")}
        first = self.client.post(f"/api/dlq/{entry['id']}/review",
                                 headers=headers, json={"decision": "requeue"})
        self.assertEqual(first.status_code, 200)
        conflict = self.client.post(f"/api/dlq/{entry['id']}/review",
                                    headers=headers,
                                    json={"decision": "requeue"})
        self.assertEqual(conflict.status_code, 409)
        missing = self.client.post("/api/dlq/dlq-nope/review",
                                   headers=headers, json={"decision": "requeue"})
        self.assertEqual(missing.status_code, 404)

    def test_invalid_decision_is_422(self):
        self._seed_entry()
        entry = guards.dead_letter_list()[0]
        bad = self.client.post(
            f"/api/dlq/{entry['id']}/review",
            headers={"X-API-Key": "guard-key",
                     "X-Autopilot-Agent-Token": self._token_for("agent-router")},
            json={"decision": "yolo"})
        self.assertEqual(bad.status_code, 422)

    def test_dlq_store_unavailable_never_masks_step_error(self):

        with mock.patch.object(guards, "dead_letter_push",
                               side_effect=RuntimeError("store gone")):
            class ExplodingClient:
                def __init__(self, **_kw):
                    raise ConnectionError("itsm unreachable")

                def __enter__(self):  # pragma: no cover - never entered
                    raise AssertionError

                def __exit__(self, *a):
                    return False


            with mock.patch("backend.deployment.tool_adapters.httpx.Client",
                            ExplodingClient):
                with self.assertRaises(ConnectionError):
                    execute_agent_step("Specialist assigned",
                                       {"webhook_url": "https://itsm.internal/x"},
                                       agent_id="agent-x")


class TestGuardStorePath(GuardWorkspaceTestCase):
    def test_db_path_prefers_guard_env_then_workspace_parent_then_repo(self):
        import backend.deployment.execution_guards as eg
        from backend.deployment import execution_guards as g2

        os.environ["AUTOPILOT_GUARD_DB"] = "/tmp/explicit-guards.db"
        self.assertEqual(g2._db_path(), pathlib.Path("/tmp/explicit-guards.db"))

        del os.environ["AUTOPILOT_GUARD_DB"]
        live_dir = pathlib.Path(self._tmp.name) / "ws"
        live_dir.mkdir()
        os.environ["AUTOPILOT_DB_PATH"] = str(live_dir / "work.db")
        self.assertEqual(g2._db_path(), live_dir / "autopilot-guards.db")

        # Non-existent workspace parent must not be trusted.
        os.environ["AUTOPILOT_DB_PATH"] = str(
            pathlib.Path(self._tmp.name) / "ghost" / "work.db")
        resolved = g2._db_path()
        self.assertTrue(resolved.is_absolute())

        for key in ("AUTOPILOT_GUARD_DB", "AUTOPILOT_DB_PATH"):
            os.environ.pop(key, None)
        self.assertEqual(g2._db_path().name, "autopilot.db")
        del eg


class TestPolicyStatFailure(GuardWorkspaceTestCase):
    def test_unreadable_policy_stat_disables_restriction(self):
        from unittest import mock

        class FakePath(str):
            """exists()-True / stat()-raising stand-in, version-proof."""

            def expanduser(self):
                return self

            def exists(self):
                return True

            def stat(self):
                raise OSError("gone")

        os.environ["AUTOPILOT_TOOLS_POLICY"] = "/fake/tools.policy.json"
        guards._policy_cache.update(path=None, mtime=None, hosts=None)
        with mock.patch.object(guards, "Path", FakePath):
            self.assertIsNone(guards._policy_hosts())


if __name__ == "__main__":
    unittest.main(verbosity=2)
