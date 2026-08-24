"""Safe tool adapter tests: tier dispatch, structural gates, webhook guard.

Pins the contract generated LangGraph workflows rely on:
- READ_ONLY formats context with zero side effects
- DRAFT_ONLY writes a local review artifact and nothing else
- INTERNAL_ACTION posts only to an operator-configured http(s) URL
- EXTERNAL_WRITE / CRITICAL_TRANSACTION raise StructuralGateError, always
"""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from backend.deployment import tool_adapters  # noqa: E402
from backend.deployment.tool_adapters import (  # noqa: E402
    StructuralGateError,
    classify_step,
    execute_agent_step,
)
from backend.models.schema import StepActionType  # noqa: E402


class TestClassification(unittest.TestCase):
    def test_known_steps_use_aps_engine_table(self):
        self.assertEqual(classify_step("Payment confirmed"), StepActionType.CRITICAL_TRANSACTION)
        self.assertEqual(classify_step("Alert triggered"), StepActionType.READ_ONLY)
        self.assertEqual(classify_step("Customer update drafted"), StepActionType.DRAFT_ONLY)
        self.assertEqual(
            classify_step("Contract sent for execution"), StepActionType.EXTERNAL_WRITE,
        )

    def test_unknown_words_fall_back_conservatively(self):
        self.assertEqual(classify_step("Wire funds release"), StepActionType.CRITICAL_TRANSACTION)
        self.assertEqual(classify_step("Send customer notification"), StepActionType.EXTERNAL_WRITE)
        self.assertEqual(classify_step("Summarize the ticket"), StepActionType.DRAFT_ONLY)
        self.assertEqual(classify_step("Update CRM record"), StepActionType.INTERNAL_ACTION)

    def test_totally_unknown_step_defaults_read_only(self):
        self.assertEqual(classify_step("Observe telemetry"), StepActionType.READ_ONLY)


class TestReadOnlyTier(unittest.TestCase):
    def test_formats_context_without_side_effects(self):
        result = execute_agent_step("Issue triaged", {"ticket": "A-1", "priority": 1})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["action_type"], "read_only")
        self.assertIn("ticket", result["observed_keys"])
        self.assertEqual(result["scalar_fields"]["priority"], 1)

    def test_result_carries_step_and_timestamp(self):
        result = execute_agent_step("Lead captured", {})
        self.assertEqual(result["step_name"], "Lead captured")
        self.assertIn("executed_at", result)


class TestDraftOnlyTier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tool_adapters.os.getenv("AUTOPILOT_DRAFT_DIR")

    def tearDown(self):
        if self._old is not None:
            tool_adapters.os.environ["AUTOPILOT_DRAFT_DIR"] = self._old
        else:
            tool_adapters.os.environ.pop("AUTOPILOT_DRAFT_DIR", None)
        self._tmp.cleanup()

    def test_writes_review_artifact_to_configured_dir(self):
        out_dir = pathlib.Path(self._tmp.name) / "drafts"
        tool_adapters.os.environ["AUTOPILOT_DRAFT_DIR"] = str(out_dir)
        result = execute_agent_step("Briefing prepared", {"deal": "Acme"})
        path = pathlib.Path(result["draft_path"])
        self.assertTrue(path.is_relative_to(out_dir))
        artifact = json.loads(path.read_text())
        self.assertEqual(artifact["status"], "pending_human_review")
        self.assertEqual(artifact["context"]["deal"], "Acme")

    def test_artifact_never_marks_itself_sent(self):
        tool_adapters.os.environ["AUTOPILOT_DRAFT_DIR"] = self._tmp.name
        result = execute_agent_step("Expansion proposal drafted", {})
        self.assertNotEqual(result["status"], "sent")
        self.assertIn("human", result["safety_note"].lower())


class TestInternalActionTier(unittest.TestCase):
    def test_requires_webhook_url(self):
        with self.assertRaises(ValueError) as ctx:
            execute_agent_step("Specialist assigned", {})
        self.assertIn("webhook_url", str(ctx.exception))

    def test_refuses_non_http_schemes(self):
        with self.assertRaises(ValueError):
            execute_agent_step("Engineer assigned", {"webhook_url": "file:///etc/passwd"})

    def test_refuses_loopback_unless_explicitly_allowed(self):
        import os

        old = os.environ.pop("AUTOPILOT_ALLOW_LOCAL_WEBHOOKS", None)
        try:
            with self.assertRaises(ValueError):
                execute_agent_step("Engineer assigned", {"webhook_url": "http://127.0.0.1:9000/hook"})
        finally:
            if old is not None:
                os.environ["AUTOPILOT_ALLOW_LOCAL_WEBHOOKS"] = old

    def test_posts_json_payload_and_reports_acceptance(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(202)

        RealClient = httpx.Client  # capture before patching

        class FakeClient:
            def __init__(self, **_kwargs):
                self._client = RealClient(transport=httpx.MockTransport(handler))

            def __enter__(self):
                return self._client

            def __exit__(self, *args):
                self._client.close()
                return False

        with mock.patch.object(tool_adapters.httpx, "Client", FakeClient):
            result = execute_agent_step(
                "Hardware provisioning requested",
                {"webhook_url": "https://itsm.internal/api/tickets"},
            )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["response_status_code"], 202)
        self.assertEqual(captured["body"]["context"]["webhook_url"],
                         "https://itsm.internal/api/tickets")


class TestStructuralGates(unittest.TestCase):
    def test_critical_transactions_cannot_execute(self):
        with self.assertRaises(StructuralGateError):
            execute_agent_step("Payment confirmed", {"amount": 10_000})

    def test_external_writes_cannot_execute(self):
        with self.assertRaises(StructuralGateError):
            execute_agent_step("Contract sent for execution", {})

    def test_gate_message_names_the_tier(self):
        with self.assertRaises(StructuralGateError) as ctx:
            execute_agent_step("Mitigation deployed", {})
        message = str(ctx.exception)
        self.assertIn("critical", message)
        self.assertIn("requires a human", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
