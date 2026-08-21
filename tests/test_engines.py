"""Engine-level and security-boundary tests beyond the happy-path suite.

Covers the pieces the lifecycle tests cannot reach: the APS fallback
classifier for open-domain step names, Monte Carlo reproducibility, webhook
payload parsing edge cases, and the API-key gate once a key is configured.
"""

import os
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.ingestion.whatsapp_connector import parse_webhook_payload  # noqa: E402
from backend.models.schema import (  # noqa: E402
    Activity,
    Process,
    StepActionType,
)
from backend.scoring.aps_engine import APSEngine  # noqa: E402
from backend.scoring.simulator import ProcessSimulator  # noqa: E402


def _process_with(step_names: list[str]) -> Process:
    base = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    return Process(
        id="process-test",
        name="Classifier Probe",
        description="synthetic process for classifier tests",
        category="general",
        activities=[
            Activity(
                id=f"act-{i}", name=name, category="general",
                actors=["tester"], timestamp=base,
            )
            for i, name in enumerate(step_names)
        ],
        metrics={
            "volume_per_month": 100,
            "avg_completion_minutes": 30.0,
            "trace_count": 10,
            "pattern_consistency": 0.9,
            "evidence_count": 20,
            "entropy_score": 0.5,
            "unique_actors_count": 2,
        },
    )


class TestApsFallbackClassifier(unittest.TestCase):
    """Unknown step names must route through the keyword heuristics safely."""

    def setUp(self):
        self.engine = APSEngine()
        self.score = self.engine.score(_process_with([
            "Wire refund to vendor",      # critical keyword -> blocked
            "Delete legacy records",      # critical keyword -> blocked
            "Draft apology note",         # draft keyword
            "Fetch order status",         # read-only keyword
            "Update CRM record",          # neutral -> internal review gate
        ]))

    def test_critical_keywords_are_blocked_from_automation(self):
        by_name = {s.step_name: s for s in self.score.step_feasibilities}
        for name in ("Wire refund to vendor", "Delete legacy records"):
            self.assertEqual(by_name[name].action_type, StepActionType.CRITICAL_TRANSACTION)
            self.assertFalse(by_name[name].is_automatable)
            self.assertTrue(by_name[name].requires_approval)
            self.assertIn(name, self.score.blocked_steps)

    def test_draft_read_and_neutral_routes(self):
        by_name = {s.step_name: s for s in self.score.step_feasibilities}
        self.assertEqual(by_name["Draft apology note"].action_type, StepActionType.DRAFT_ONLY)
        self.assertTrue(by_name["Draft apology note"].requires_approval)
        self.assertEqual(by_name["Fetch order status"].action_type, StepActionType.READ_ONLY)
        self.assertFalse(by_name["Fetch order status"].requires_approval)
        self.assertEqual(by_name["Update CRM record"].action_type, StepActionType.INTERNAL_ACTION)
        # Neutral steps land at exactly 0.70 -- automatable in principle, but
        # always behind a review gate.
        self.assertEqual(by_name["Update CRM record"].feasibility_score, 0.70)
        self.assertTrue(by_name["Update CRM record"].requires_approval)

    def test_catalog_steps_take_precedence_over_heuristics(self):
        known = self.engine.score(_process_with(["Alert triggered"]))
        step = known.step_feasibilities[0]
        self.assertEqual(step.feasibility_score, 0.98)  # table value, not 0.95 heuristic

    def test_empty_process_scores_without_crashing(self):
        score = self.engine.score(_process_with([]))
        self.assertGreaterEqual(score.score, 0.0)
        self.assertEqual(score.deployable_pct, 0.0)


class TestSimulatorDeterminism(unittest.TestCase):
    def setUp(self):
        self.process = _process_with(["Read ticket", "Draft response"])
        self.score = APSEngine().score(self.process)

    def test_same_seed_reproduces_exactly(self):
        first = ProcessSimulator().simulate(self.process, self.score, runs=200, seed=7)
        second = ProcessSimulator().simulate(self.process, self.score, runs=200, seed=7)
        self.assertEqual(first, second)

    def test_rates_are_complementary_and_bounded(self):
        result = ProcessSimulator().simulate(self.process, self.score, runs=500, seed=3)
        self.assertAlmostEqual(
            result.straight_through_rate + result.human_escalation_rate, 100.0, delta=0.01)
        self.assertGreaterEqual(result.straight_through_rate, 0.0)

    def test_blocked_process_never_runs_straight_through(self):
        blocked = _process_with(["Wire refund to vendor"])
        blocked_score = APSEngine().score(blocked)
        result = ProcessSimulator().simulate(blocked, blocked_score, runs=100, seed=11)
        self.assertEqual(result.straight_through_rate, 0.0)
        self.assertGreaterEqual(result.safety_violations_caught, 1)


class TestWhatsAppPayloadParsing(unittest.TestCase):
    def test_text_message_is_ingested(self):
        payload = {"entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "pn-1"},
            "messages": [{"id": "m1", "from": "15551234", "timestamp": "1755772800",
                          "type": "text", "text": {"body": "hello"}}],
        }}]}]}
        messages = parse_webhook_payload(payload)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, "hello")
        self.assertEqual(messages[0].channel_id, "whatsapp:pn-1")

    def test_invalid_timestamp_falls_forward_to_now(self):
        payload = {"entry": [{"changes": [{"value": {"messages": [
            {"id": "m2", "from": "x", "timestamp": "not-a-number", "type": "text",
             "text": {"body": "hi"}},
        ]}}]}]}
        messages = parse_webhook_payload(payload)
        self.assertEqual(len(messages), 1)
        self.assertIsNotNone(messages[0].timestamp)

    def test_phone_number_id_filter_excludes_other_numbers(self):
        payload = {"entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "other"},
            "messages": [{"id": "m3", "from": "x", "timestamp": "1755772800",
                          "type": "text", "text": {"body": "hi"}}],
        }}]}]}
        self.assertEqual(parse_webhook_payload(payload, expected_phone_number_id="pn-1"), [])
        self.assertEqual(len(parse_webhook_payload(payload)), 1)

    def test_unsupported_type_gets_placeholder(self):
        payload = {"entry": [{"changes": [{"value": {"messages": [
            {"id": "m4", "from": "x", "timestamp": "1755772800", "type": "hsm"},
        ]}}]}]}
        messages = parse_webhook_payload(payload)
        self.assertEqual(messages[0].content, "[unsupported message type]")


class TestTimelineEndpoint(unittest.TestCase):
    """The timeline route must 404 cleanly instead of crashing on None."""

    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "test.db"
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        import asyncio

        self._ctx.__exit__(None, None, None)
        asyncio.new_event_loop().run_until_complete(database_close())
        self._tmp.cleanup()

    def test_unknown_process_returns_404(self):
        r = self.client.get("/api/processes/process-does-not-exist/timeline")
        self.assertEqual(r.status_code, 404)

    def test_known_process_returns_sorted_timeline(self):
        processes = self.client.get("/api/processes/").json()
        target = processes[0]
        r = self.client.get(f"/api/processes/{target['id']}/timeline")
        self.assertEqual(r.status_code, 200)
        stamps = [item["timestamp"] for item in r.json()]
        self.assertEqual(stamps, sorted(stamps))
        if r.json():
            self.assertIn("evidence", r.json()[0])


async def database_close():
    import backend.database as database

    await database.close_db()


class TestApiKeyGate(unittest.TestCase):
    """With AUTOPILOT_API_KEY configured, mutating endpoints demand the header."""

    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "test.db"
        os.environ["AUTOPILOT_API_KEY"] = "test-key-123"
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        import asyncio

        self._ctx.__exit__(None, None, None)
        asyncio.new_event_loop().run_until_complete(self._db.close_db())
        self._tmp.cleanup()
        os.environ.pop("AUTOPILOT_API_KEY", None)

    def test_mutating_endpoint_rejects_missing_key(self):
        r = self.client.post("/api/processes/discover")
        self.assertEqual(r.status_code, 401)

    def test_mutating_endpoint_rejects_wrong_key(self):
        r = self.client.post("/api/processes/discover",
                             headers={"X-API-Key": "wrong"})
        self.assertEqual(r.status_code, 401)

    def test_mutating_endpoint_accepts_correct_key(self):
        r = self.client.post("/api/processes/discover",
                             headers={"X-API-Key": "test-key-123"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("processes", r.json())

    def test_reads_stay_open_while_writes_are_gated(self):
        r = self.client.get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
