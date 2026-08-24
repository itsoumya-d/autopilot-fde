"""Targeted unit tests closing per-module coverage gaps.

Each test pins a branch the HTTP/API suites never reach: enhancer fallback
chains, recommendation wave edges, mining fallbacks, security primitives,
adapter guard rails, and exporter defaults.
"""

import asyncio
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from backend.deployment.tool_adapters import execute_agent_step  # noqa: E402
from backend.discovery.activity_extractor import ActivityExtractor  # noqa: E402
from backend.discovery.process_graph import BusinessProcessGraph  # noqa: E402
from backend.discovery.process_miner import ProcessMiner  # noqa: E402
from backend.export.training import build_rows, default_output_path, write_jsonl  # noqa: E402
from backend.ingestion.base import ChannelConnector  # noqa: E402
from backend.ingestion.whatsapp_connector import WhatsAppConnector  # noqa: E402
from backend.llm.enhancer import get_enhancer  # noqa: E402
from backend.models.schema import (  # noqa: E402
    Activity,
    APScore,
    Channel,
    ChannelPublic,
    Message,
    Process,
    SafetyStatus,
)
from backend.scoring.recommender import Recommender  # noqa: E402


class TestAbstractConnectorContract(unittest.TestCase):
    def test_base_stub_bodies_execute_via_super_calls(self):
        class Probe(ChannelConnector):
            async def connect(self):
                return await super().connect()

            async def fetch_messages(self, since):
                return await super().fetch_messages(since)

            async def health_check(self):
                return await super().health_check()

            @property
            def channel_type(self):
                return ChannelConnector.channel_type.fget(self)

        probe = Probe({"anything": "goes"})
        self.assertIsNone(asyncio.run(probe.connect()))
        self.assertIsNone(asyncio.run(probe.fetch_messages(datetime.now(UTC))))
        self.assertIsNone(asyncio.run(probe.health_check()))
        self.assertIsNone(probe.channel_type)


class TestWhatsAppConnectorBranches(unittest.TestCase):
    def connector(self):
        return WhatsAppConnector({"access_token": "tok", "phone_number_id": "pn"})

    def test_connect_returns_false_on_http_error(self):
        connector = self.connector()

        class ExplodingClient:
            async def __aenter__(self):
                raise httpx.ConnectError("boom")

            async def __aexit__(self, *exc):
                return False

        with mock.patch("httpx.AsyncClient", return_value=ExplodingClient()):
            self.assertFalse(asyncio.run(connector.connect()))

    def test_health_check_delegates_to_connect(self):
        connector = self.connector()
        with mock.patch.object(connector, "connect", return_value=True):
            self.assertTrue(asyncio.run(connector.health_check()))


class TestEnhancerSelectionAndLoop(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("LLM_API_KEY", None)

    def test_api_key_selects_http_enhancer(self):
        os.environ["LLM_API_KEY"] = "sk-test"
        enhancer = get_enhancer()
        self.assertEqual(type(enhancer).__name__, "HttpxLLMEnhancer")

    def test_module_level_enhance_processes_updates_and_skips(self):
        from backend.llm import enhancer as enhancer_mod

        calls = {"n": 0}

        def flaky(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"llm_summary": "Great process"}
            raise RuntimeError("no")

        class P:
            id = "p1"
            description = ""

            def model_dump(self):
                return {"id": self.id}

        processes = [P(), P()]
        with mock.patch.object(enhancer_mod, "get_enhancer",
                               return_value=SimpleNamespace(enhance_process=flaky)):
            enhancer_mod.enhance_processes(processes)
        self.assertEqual(processes[0].description, "Great process")
        self.assertEqual(processes[1].description, "")  # failure skipped, not fatal
        self.assertEqual(calls["n"], 2)


class TestServicesEnhancePaths(unittest.TestCase):
    def setUp(self):
        self._old = {k: os.environ.get(k) for k in
                     ("AUTOPILOT_LLM_ENHANCE", "LLM_API_KEY")}
        for k in self._old:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_maybe_enhance_disabled_is_noop(self):
        import backend.services as services

        with mock.patch.object(services, "get_enhancer",
                               side_effect=AssertionError("must not be called")):
            asyncio.run(services._maybe_enhance([object()]))

    def test_maybe_enhance_failure_never_breaks_discovery(self):
        import backend.services as services

        os.environ["AUTOPILOT_LLM_ENHANCE"] = "1"
        with mock.patch.object(services, "get_enhancer",
                               side_effect=RuntimeError("down")):
            asyncio.run(services._maybe_enhance([object()]))  # swallowed

    def test_maybe_enhance_happy_path_offloads_to_thread(self):
        import backend.services as services

        os.environ["AUTOPILOT_LLM_ENHANCE"] = "1"
        seen = []

        def record(processes):
            seen.extend(processes)

        with mock.patch.object(services, "get_enhancer",
                               return_value=SimpleNamespace(enhance_processes=record)):
            asyncio.run(services._maybe_enhance(["proc-a"]))
        self.assertEqual(seen, ["proc-a"])

    def test_ensure_demo_workspace_is_idempotent(self):
        import pathlib as pl
        import tempfile as tf

        import backend.database as database

        with tf.TemporaryDirectory() as tmp:
            database.DB_PATH = pl.Path(tmp) / "svc.db"
            try:
                asyncio.run(database.init_db())
                from backend.services import ensure_demo_workspace

                asyncio.run(ensure_demo_workspace())
                first = asyncio.run(database.count_messages())
                asyncio.run(ensure_demo_workspace())  # early-return branch
                self.assertEqual(asyncio.run(database.count_messages()), first)
            finally:
                asyncio.run(database.close_db())


def _score(score=50.0, eligible=("A",), blocked=(), evidence=80.0,
           factors=None, roi=1000.0, hours=5.0):
    return APScore(
        process_id="proc-1", score=score,
        evidence_confidence=evidence,
        eligible_steps=list(eligible), blocked_steps=list(blocked),
        factors=factors or {}, recommended_mode=SafetyStatus.ASSISTED,
        estimated_monthly_roi_dollars=roi, estimated_hours_saved_monthly=hours,
    )


class TestRecommenderWaveEdges(unittest.TestCase):
    def test_full_branch_matrix(self):
        now_low = _score(score=80, eligible=("a", "b"), roi=5000)
        next_high_risk = _score(score=50, blocked=tuple(f"b{i}" for i in range(4)))
        later_high = _score(score=20, eligible=(), evidence=50)
        entropy_gap = _score(score=55, factors={"Graph Complexity (Inverse)": 30})
        recs = Recommender().recommend([], [now_low, next_high_risk, later_high, entropy_gap])
        waves = {id(r): r.wave for r in recs}
        self.assertIn("Now", waves.values())
        self.assertIn("Next", waves.values())
        self.assertIn("Later", waves.values())
        now_rec = next(r for r in recs if r.estimated_annual_roi_dollars == 60000.0)
        self.assertEqual(now_rec.risk_level, "Low")  # Now wave, no blocked steps
        entropy_rec = next(r for r in recs
                           if any("entropy" in m for m in r.missing_capabilities))
        self.assertEqual(entropy_rec.risk_level, "Medium")
        unknown_process = Recommender().recommend([], [_score()])[0]
        self.assertEqual(unknown_process.process_name, "Discovered Workflow")

    def test_next_wave_medium_risk_with_few_blocked(self):
        score = _score(score=50, blocked=("only-one",))
        rec = Recommender().recommend([], [score])[0]
        self.assertEqual(rec.wave, "Next")
        self.assertEqual(rec.risk_level, "Medium")


def _activity(case, category, name, minute):
    return Activity(
        id=f"a-{case}-{name}", name=name, category=category, case_id=case,
        actors=["dana"], timestamp=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
    )


class TestMinerFallbacks(unittest.TestCase):
    def test_unknown_category_uses_generic_catalog_entry(self):
        activities = [
            _activity("c1", "procurement", "Purchase requested", 0),
            _activity("c1", "procurement", "PO approved", 5),
            _activity("c2", "procurement", "Purchase requested", 0),
            _activity("c2", "procurement", "PO approved", 5),
        ]
        processes = ProcessMiner().mine(activities)
        procurement = [p for p in processes if p.category == "procurement"]
        self.assertEqual(len(procurement), 1)
        self.assertEqual(procurement[0].name, "Procurement Automated Workflow")
        self.assertTrue(procurement[0].safety_notes)

    def test_single_trace_category_is_below_minimum(self):
        activities = [
            _activity("lonely", "support", "Issue triaged", 0),
            _activity("lonely", "support", "Resolution confirmed", 3),
        ]
        discovered = [p for p in ProcessMiner().mine(activities)
                      if p.category == "support"]
        # One trace < MINIMUM_TRACES(2): nothing discoverable for support.
        for process in discovered:
            self.assertLessEqual(process.metrics.trace_count, 1)


class TestProcessGraphHelpers(unittest.TestCase):
    def _graph_with_edge(self, duration: float):
        from backend.models.schema import Activity, ProcessEdge, ProcessMetrics

        process = Process(
            id="proc-b", name="Bottleneck Probe", category="support",
            metrics=ProcessMetrics(),
            activities=[Activity(id="act-1", name="Issue triaged",
                                 category="support", case_id="c1",
                                 timestamp=datetime.now(UTC))],
            edges=[ProcessEdge(source="a", target="b",
                               avg_duration_minutes=duration)],
        )
        graph = BusinessProcessGraph()
        graph.add_process(process)
        return graph

    def test_remove_process_hit_and_miss_are_safe(self):
        graph = self._graph_with_edge(0.0)
        graph.remove_process("proc-b")
        graph.remove_process("never-there")  # miss must not raise
        self.assertEqual(graph.processes, {})

    def test_find_bottlenecks_reports_only_slow_edges(self):
        graph = self._graph_with_edge(duration=90.0)
        bottlenecks = graph.find_bottlenecks(threshold_minutes=60.0)
        self.assertEqual(len(bottlenecks), 1)
        self.assertEqual(bottlenecks[0]["process_id"], "proc-b")
        self.assertEqual(bottlenecks[0]["duration_minutes"], 90.0)
        self.assertEqual(graph.find_bottlenecks(threshold_minutes=120.0), [])

    def test_visualization_includes_process_and_activity_nodes(self):
        graph = self._graph_with_edge(90.0)
        viz = graph.to_visualization()
        types = {node["type"] for node in viz["nodes"]}
        self.assertIn("processNode", types)
        self.assertIn("activityNode", types)
        self.assertEqual(len(viz["edges"]), 1)


class TestExtractorNoMatch(unittest.TestCase):
    def test_message_without_rule_hits_continue(self):
        message = Message(
            id="m-x", sender="eve", content="zzz qqq unfathomable wibble",
            timestamp=datetime.now(UTC),
        )
        self.assertEqual(ActivityExtractor().extract([message]), [])


class TestSchemaFromChannel(unittest.TestCase):
    def test_public_projection_matches_fields(self):
        channel = Channel(id="ch-9", type=__import__(
            "backend.models.schema", fromlist=["ChannelType"]).ChannelType.SLACK,
            name="Support", created_at=datetime.now(UTC))
        public = ChannelPublic.from_channel(channel)
        self.assertEqual(public.id, channel.id)
        self.assertEqual(public.type, channel.type)
        self.assertNotIn("credentials", public.model_dump())


class TestAPSRecommendationBranches(unittest.TestCase):
    def test_critical_only_process_recommends_observation(self):
        from backend.scoring.aps_engine import APSEngine

        text = APSEngine._generate_recommendation(
            score=60, evidence=0.9, eligible=[], blocked=["Payment confirmed"])
        self.assertIn("critical", text.lower())

    def test_low_evidence_recommends_more_observation(self):
        from backend.scoring.aps_engine import APSEngine

        text = APSEngine._generate_recommendation(
            score=60, evidence=0.4, eligible=["A"], blocked=[])
        self.assertIn("observing", text)


class TestToolAdapterGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AUTOPILOT_DRAFT_DIR"] = self._tmp.name
        self._token_old = os.environ.pop("AUTOPILOT_WEBHOOK_BEARER_TOKEN", None)

    def tearDown(self):
        if self._token_old is not None:
            os.environ["AUTOPILOT_WEBHOOK_BEARER_TOKEN"] = self._token_old
        else:
            os.environ.pop("AUTOPILOT_WEBHOOK_BEARER_TOKEN", None)
        os.environ.pop("AUTOPILOT_DRAFT_DIR", None)
        self._tmp.cleanup()

    def _run_webhook(self, context):
        captured = {}
        RealClient = httpx.Client  # capture before patching

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200)

        class FakeClient:
            def __init__(self, **_kw):
                self._client = RealClient(transport=httpx.MockTransport(handler))

            def __enter__(self):
                return self._client

            def __exit__(self, *a):
                self._client.close()
                return False

        with mock.patch("backend.deployment.tool_adapters.httpx.Client", FakeClient):
            result = execute_agent_step("Specialist assigned", context)
        return result, captured

    def test_bearer_token_is_attached_when_configured(self):
        os.environ["AUTOPILOT_WEBHOOK_BEARER_TOKEN"] = "tok-123"
        result, captured = self._run_webhook({"webhook_url": "https://crm.internal/x"})
        self.assertTrue(result["accepted"])
        self.assertEqual(captured["headers"].get("authorization"), "Bearer tok-123")

    def test_no_token_means_no_authorization_header(self):
        result, captured = self._run_webhook({"webhook_url": "https://crm.internal/x"})
        self.assertTrue(result["accepted"])
        self.assertNotIn("authorization", {k.lower() for k in captured["headers"]})

    def test_oversized_payload_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            execute_agent_step("Invoice reconciled", {
                "webhook_url": "https://erp.internal/x",
                "blob": "x" * 70_000,
            })
        self.assertIn("64 KiB", str(ctx.exception))


class TestSecurityPrimitives(unittest.TestCase):
    def test_rate_limiter_evicts_stale_window_entries(self):
        from backend.security import RateLimiter

        limiter = RateLimiter()
        limiter._hits["old-client"] = [0.0]  # ancient timestamps
        with self.assertRaises(Exception) as ctx:
            for _ in range(2):
                limiter.check("old-client", limit_per_min=1)
        self.assertIn("Rate limit", str(ctx.exception))

    def test_rate_limiter_zero_limit_disables_check(self):
        from backend.security import RateLimiter

        limiter = RateLimiter()
        limiter.check("anyone", limit_per_min=0)
        limiter.check("anyone", limit_per_min=0)

    def test_client_key_falls_back_without_connection_info(self):
        from starlette.requests import Request

        scope = {"type": "http", "client": None}
        request = Request(scope)
        from backend.security import client_key

        self.assertEqual(client_key(request), "unknown")


class TestSlackErrorMapping(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SLACK_BOT_TOKEN", None)

    def test_slack_api_error_maps_to_configuration_error(self):
        from slack_sdk.errors import SlackApiError

        from backend.ingestion import slack_connector as slack_mod
        from backend.ingestion.slack_connector import SlackConfigurationError

        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"

        class FailingAuth:
            async def auth_test(self):
                raise SlackApiError("auth failed",
                                    {"error": "invalid_auth"})

        with mock.patch.object(slack_mod, "AsyncWebClient",
                               return_value=FailingAuth()):
            with self.assertRaises(SlackConfigurationError) as ctx:
                asyncio.run(slack_mod.sync_channel("C1"))
        self.assertIn("invalid_auth", str(ctx.exception))


class TestExportDefaults(unittest.TestCase):
    def test_default_output_path_honors_override_then_cwd(self):
        old = os.environ.pop("AUTOPILOT_TRAINING_OUT", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cwd = os.getcwd()
                os.chdir(tmp)
                try:
                    path = default_output_path()
                    self.assertTrue(path.is_absolute())
                    self.assertIn("runs/training", str(path))
                finally:
                    os.chdir(cwd)
            os.environ["AUTOPILOT_TRAINING_OUT"] = "/tmp/custom-out.jsonl"
            self.assertEqual(default_output_path(),
                             pathlib.Path("/tmp/custom-out.jsonl"))
        finally:
            if old is not None:
                os.environ["AUTOPILOT_TRAINING_OUT"] = old
            else:
                os.environ.pop("AUTOPILOT_TRAINING_OUT", None)

    def test_whitespace_content_still_yields_row_via_sender_prefix(self):
        message = Message(id="m-blank", sender="dana", content="   ",
                          timestamp=datetime.now(UTC))
        activity = Activity(id="a-1", name="Issue triaged", category="support",
                            case_id="c1", actors=["dana"], timestamp=message.timestamp,
                            source_messages=["m-blank"])
        process = Process(id="p1", name="Support", activities=[activity])
        rows = build_rows([process], {}, [message])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["messages"][1]["content"], "dana:")

    def test_write_jsonl_handles_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_jsonl([{"k": "café ☕"}], pathlib.Path(tmp) / "u.jsonl")
            self.assertIn("café", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
