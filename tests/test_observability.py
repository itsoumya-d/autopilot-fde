"""v0.5.0 Observable & Compliant: gen_ai.* spans + tamper-evident audit chain."""

import asyncio
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.deployment.tool_adapters import (  # noqa: E402
    StructuralGateError,
    execute_agent_step,
)
from backend.export.audit_chain import (  # noqa: E402
    GENESIS_PREV_HASH,
    chain_events,
    export_agent_chain,
    verify_chain,
)


class RecordingSpan:
    def __init__(self):
        self.attributes: dict = {}
        self.exceptions: list[BaseException] = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, error):
        self.exceptions.append(error)


class RecordingTracer:
    def __init__(self):
        self.spans: list[RecordingSpan] = []

    def start_as_current_span(self, name):
        span = RecordingSpan()
        span.name = name
        self.spans.append(span)
        return self._cm(span)

    class _cm:
        def __init__(self, span):
            self.span = span

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc, tb):
            return False


class TestToolSpan(unittest.TestCase):
    def run_under(self, tracer_obj):
        import backend.observability.tracing as tracing

        with mock.patch.object(tracing, "tracer", return_value=tracer_obj), \
             mock.patch.object(tracing, "configured_model",
                               return_value="gpt-test"):
            return execute_agent_step(
                "Issue triaged", {"ticket": "A-1"},
                agent_id="agent-x",
                )

    def test_span_carries_genai_conventions(self):
        recorder = RecordingTracer()
        result = self.run_under(recorder)
        self.assertEqual(result["status"], "completed")
        span = recorder.spans[0]
        self.assertEqual(span.name, "autopilot.tool.adapter.read_only")
        self.assertEqual(span.attributes["gen_ai.system"], "autopilot-fde")
        self.assertEqual(span.attributes["gen_ai.tool.name"],
                         "adapter.read_only")
        self.assertEqual(span.attributes["gen_ai.agent.id"], "agent-x")
        self.assertEqual(span.attributes["autopilot.step.name"], "Issue triaged")
        self.assertEqual(span.attributes["gen_ai.request.model"], "gpt-test")

    def test_token_usage_attaches_when_provided(self):
        recorder = RecordingTracer()
        import backend.observability.tracing as tracing

        with mock.patch.object(tracing, "tracer", return_value=recorder), \
             mock.patch.object(tracing, "configured_model", return_value=None):
            execute_agent_step("Lead captured", {
                "token_usage": (120, 30),
            })
        usage = recorder.spans[0].attributes
        self.assertEqual(usage.get("gen_ai.usage.input_tokens"), 120)
        self.assertEqual(usage.get("gen_ai.usage.output_tokens"), 30)
        self.assertNotIn("gen_ai.request.model", usage)

    def test_gate_error_recorded_on_span_before_raise(self):
        recorder = RecordingTracer()
        import backend.observability.tracing as tracing

        with mock.patch.object(tracing, "tracer", return_value=recorder):
            with self.assertRaises(StructuralGateError):
                execute_agent_step("Payment confirmed", {})
        self.assertEqual(len(recorder.spans[0].exceptions), 1)

    def test_noop_fallback_matches_surface_without_otel(self):
        from backend.observability.tracing import _NoopSpan, tool_span

        with mock.patch("backend.observability.tracing._TRACING_AVAILABLE", False):
            with tool_span("adapter.read_only", step_name="s",
                           agent_id="a") as span:
                span.set_attribute("gen_ai.tool.name", "x")  # must not raise
                span.set_token_usage(1, 2)
                span.record_exception(ValueError())
        self.assertIsInstance(span, _NoopSpan)
        # Direct surface parity (tool_span shadows set_token_usage with the
        # real closure, so exercise the noop's own methods explicitly).
        bare = _NoopSpan()
        bare.set_token_usage(3, 4)
        bare.record_exception(RuntimeError("noop"))
        bare.set_attribute("k", "v")

    def test_configured_model_reflects_env_both_ways(self):
        import backend.observability.tracing as tracing

        old = {k: os.environ.get(k) for k in
               ("AUTOPILOT_LLM_ENHANCE", "LLM_MODEL")}
        try:
            os.environ.pop("AUTOPILOT_LLM_ENHANCE", None)
            self.assertIsNone(tracing.configured_model())
            os.environ["AUTOPILOT_LLM_ENHANCE"] = "1"
            os.environ.pop("LLM_MODEL", None)
            self.assertEqual(tracing.configured_model(), "unspecified")
            os.environ["LLM_MODEL"] = "gpt-x"
            self.assertEqual(tracing.configured_model(), "gpt-x")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _reload_tracing_with(self, otel_module):
        """Reload tracing against a stubbed/absent otel package.

        Returns a snapshot of the reloaded state; modules are restored in
        finally, so callers must assert against the snapshot only.
        """
        import importlib

        import backend.observability.tracing as tracing

        saved = dict(sys.modules)
        try:
            if otel_module is None:
                sys.modules["opentelemetry"] = None  # forces ImportError
            else:
                sys.modules["opentelemetry"] = otel_module
            reloaded = importlib.reload(tracing)
            return {
                "available": reloaded._TRACING_AVAILABLE,
                "otel": reloaded._otel_trace,
                "tracer_result": reloaded.tracer(),
            }
        finally:
            sys.modules.clear()
            sys.modules.update(saved)
            importlib.reload(tracing)

    def test_installed_path_uses_real_tracer_factory(self):
        import types

        stub = types.ModuleType("opentelemetry")
        stub.trace = SimpleNamespace(get_tracer=lambda name: ("real", name))
        snapshot = self._reload_tracing_with(stub)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["tracer_result"], ("real", "autopilot-fde"))

    def test_missing_extra_sets_unavailable_flag(self):
        snapshot = self._reload_tracing_with(None)
        self.assertFalse(snapshot["available"])
        self.assertIsNone(snapshot["otel"])


EVENTS = [
    {"action": "deploy", "actor": "alice", "at": "2026-08-24T00:00:00Z"},
    {"action": "approve", "actor": "bob", "at": "2026-08-24T00:05:00Z"},
    {"action": "stop", "actor": "carol", "at": "2026-08-24T00:10:00Z"},
]


class TestAuditChain(unittest.TestCase):
    def test_chain_roundtrip_verifies_clean(self):
        chained = chain_events(EVENTS)
        ok, reason = verify_chain(chained)
        self.assertTrue(ok, reason)
        self.assertEqual(chained[0]["prev_hash"], GENESIS_PREV_HASH)
        self.assertTrue(all(r["event"] == e for r, e in zip(chained, EVENTS)))

    def test_tampered_event_breaks_chain_at_that_position(self):
        chained = chain_events(EVENTS)
        chained[1]["event"]["actor"] = "mallory"
        ok, reason = verify_chain(chained)
        self.assertFalse(ok)
        self.assertIn("position 1", reason)

    def test_reorder_is_detected_via_seq(self):
        chained = chain_events(EVENTS)
        chained[0], chained[1] = chained[1], chained[0]
        ok, reason = verify_chain(chained)
        self.assertFalse(ok)

    def test_prev_hash_tampering_is_detected(self):
        chained = chain_events(EVENTS)
        chained[2]["prev_hash"] = "a" * 64
        ok, reason = verify_chain(chained)
        self.assertFalse(ok)
        self.assertIn("prev_hash", reason)

    def test_truncated_hash_field_fails(self):
        chained = chain_events(EVENTS)
        chained[2]["hash"] = "f" * 64
        ok, reason = verify_chain(chained)
        self.assertFalse(ok)
        self.assertIn("position 2", reason)

    def test_export_envelope_shape_and_empty_trail(self):
        envelope = export_agent_chain("agent-z", EVENTS)
        self.assertEqual(envelope["head_hash"], chained_head(envelope))
        self.assertEqual(envelope["algorithm"], "sha256-canonical-json")
        self.assertEqual(envelope["event_count"], 3)
        ok, _ = verify_chain(envelope["events"])
        self.assertTrue(ok)

        empty = export_agent_chain("agent-empty", [])
        self.assertEqual(empty["head_hash"], GENESIS_PREV_HASH)
        self.assertEqual(empty["event_count"], 0)

    def test_genesis_link_constant_shape(self):
        self.assertEqual(len(GENESIS_PREV_HASH), 64)
        int(GENESIS_PREV_HASH, 16)  # hex


def chained_head(envelope):
    return envelope["events"][-1]["hash"]


class TestAuditChainEndpoint(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "chain.db"
        from fastapi.testclient import TestClient

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

    def _deploy_first_process(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Chain Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]}})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_endpoint_returns_verifiable_chain(self):
        agent = self._deploy_first_process()
        self.client.post(f"/api/agents/{agent['id']}/approve")
        exported = self.client.get(f"/api/agents/{agent['id']}/audit-chain")
        self.assertEqual(exported.status_code, 200)
        envelope = exported.json()
        self.assertEqual(envelope["event_count"], 2)  # deploy + approve
        ok, reason = verify_chain(envelope["events"])
        self.assertTrue(ok, reason)
        actions = [r["event"]["action"] for r in envelope["events"]]
        self.assertEqual(actions, ["deploy", "approve"])

    def test_endpoint_404_for_missing_agent(self):
        self.assertEqual(
            self.client.get("/api/agents/agent-missing/audit-chain").status_code,
            404)

    def test_corrupt_audit_still_exports_empty_verified_chain(self):
        agent = self._deploy_first_process()
        raw = asyncio.run(self._db.get_agent(agent["id"]))
        raw.metrics["audit"] = "corrupted"
        asyncio.run(self._db.save_agent(raw))
        exported = self.client.get(f"/api/agents/{raw.id}/audit-chain")
        envelope = exported.json()
        self.assertEqual(envelope["event_count"], 0)
        ok, _ = verify_chain(envelope["events"])
        self.assertTrue(ok)


class TestDashboardCostRollups(unittest.TestCase):
    def test_summary_includes_token_cost_fields(self):
        import tempfile as tf

        import backend.database as database

        with tf.TemporaryDirectory() as tmp_dir:
            database.DB_PATH = pathlib.Path(tmp_dir) / "roll.db"
            try:
                asyncio.run(database.init_db())
                from datetime import datetime as dt

                from backend.models.schema import (
                    AgentBranch,
                    AgentStatus,
                    APScore,
                    DeploymentConfig,
                    SafetyStatus,
                )

                asyncio.run(database.replace_discovery_results([], [
                    APScore(process_id="p1", score=70,
                            recommended_mode=SafetyStatus.ASSISTED,
                            factors={"estimated_monthly_token_cost": 12.5}),
                ]))
                asyncio.run(database.create_agent(AgentBranch(
                    id="agent-tok", process_id="p1", name="Token Copilot",
                    status=AgentStatus.RUNNING, config=DeploymentConfig(),
                    metrics={"total_tokens_consumed": 4321})))
                summary = asyncio.run(database.dashboard_summary())
                self.assertEqual(summary.estimated_monthly_token_cost_dollars, 12.5)
                self.assertEqual(summary.agent_tokens_consumed, 4321)
                del dt
            finally:
                asyncio.run(database.close_db())


if __name__ == "__main__":
    unittest.main(verbosity=2)
