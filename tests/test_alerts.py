"""v0.11.0 Intersection Alerts: deterministic rules over the object log."""

import asyncio
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.discovery.alerts import (  # noqa: E402
    DEFAULTS,
    _load_policy,
    evaluate_alerts,
)
from backend.discovery.object_centric import build_object_log  # noqa: E402
from backend.models.schema import Activity, Message  # noqa: E402


def _log(rows):
    """rows: list of (case, name, actors, content) -> built object log."""
    activities, messages = [], []
    for index, (case, name, actors, content) in enumerate(rows):
        mid = f"m-{index}"
        messages.append(Message(id=mid, channel_id="ch", sender=actors[0],
                                content=content,
                                timestamp=datetime(2026, 8, 24, 10, index,
                                                   tzinfo=UTC)))
        activities.append(Activity(
            id=f"a-{index}", name=name, category="ops", case_id=case,
            actors=list(actors),
            timestamp=datetime(2026, 8, 24, 10, index, tzinfo=UTC),
            source_messages=[mid], confidence=0.9))
    return build_object_log(activities, messages)


class TestSharedObjectRule(unittest.TestCase):
    def test_vendor_spanning_two_cases_warns_with_sorted_evidence(self):
        log = _log([
            ("case-1", "Invoice exception received", ("dana",),
             "vendor Acme invoice received"),
            ("case-2", "Invoice reconciled", ("eve",),
             "vendor Acme reconciled"),
        ])
        alerts = evaluate_alerts(log)
        shared = [a for a in alerts if a["rule_id"] == "shared_object_across_cases"]
        self.assertEqual(len(shared), 1)
        alert = shared[0]
        self.assertEqual(alert["severity"], "warn")
        self.assertEqual(alert["object_id"], "vendor:acme")
        self.assertEqual(alert["object_type"], "vendor")
        self.assertIn("spans 2 cases", alert["message"])
        self.assertEqual(alert["event_ids"],
                         sorted(e["id"] for e in log["events"]
                                if any(r["objectId"] == "vendor:acme"
                                       for r in e["relationships"])))

    def test_single_case_vendor_does_not_alert(self):
        log = _log([("case-1", "Invoice received", ("dana",), "vendor Acme x")])
        self.assertEqual([a for a in evaluate_alerts(log)
                          if a["rule_id"] == "shared_object_across_cases"], [])

    def test_case_and_actor_types_are_excluded_from_rule(self):
        # Two events share the same actor across two cases; only vendor alerts.
        log = _log([
            ("case-1", "Issue triaged", ("dana",), "plain text one"),
            ("case-2", "Resolution confirmed", ("dana",), "plain text two"),
        ])
        shared = [a for a in evaluate_alerts(log)
                  if a["rule_id"] == "shared_object_across_cases"]
        self.assertEqual(shared, [])


class TestAmountRule(unittest.TestCase):
    def test_amount_at_threshold_is_critical(self):
        log = _log([("case-1", "Payment confirmed", ("dana",),
                     "$10,000.00 wired")])
        alerts = [a for a in evaluate_alerts(log)
                  if a["rule_id"] == "large_amount_observed"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "critical")
        self.assertEqual(alerts[0]["object_id"], "amount:$10000.00")

    def test_small_amount_stays_silent(self):
        log = _log([("case-1", "Payment confirmed", ("dana",), "$9,999 wire")])
        self.assertEqual([a for a in evaluate_alerts(log)
                          if a["rule_id"] == "large_amount_observed"], [])


class TestHubActorRule(unittest.TestCase):
    def test_actor_crossing_min_events_is_info(self):
        rows = [(f"case-{i}", "Issue triaged", ("hub",), f"text {i}")
                for i in range(5)]
        alerts = [a for a in evaluate_alerts(_log(rows))
                  if a["rule_id"] == "hub_actor"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "info")
        self.assertEqual(len(alerts[0]["event_ids"]), 5)

    def test_below_hub_threshold_is_silent(self):
        rows = [("case-1", "Issue triaged", ("quiet",), "a"),
                ("case-1", "Resolution confirmed", ("quiet",), "b")]
        hub = [a for a in evaluate_alerts(_log(rows))
               if a["rule_id"] == "hub_actor"]
        self.assertEqual(hub, [])


class TestPolicyAndOrdering(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.pop("AUTOPILOT_ALERTS_POLICY", None)

    def tearDown(self):
        if self._old is not None:
            os.environ["AUTOPILOT_ALERTS_POLICY"] = self._old
        else:
            os.environ.pop("AUTOPILOT_ALERTS_POLICY", None)
        self._tmp.cleanup()

    def test_policy_overrides_defaults(self):
        policy_path = pathlib.Path(self._tmp.name) / "alerts.json"
        policy_path.write_text(json.dumps({"rules": {
            "large_amount_observed": {"min_dollars": 100},
            "shared_object_across_cases": {"min_cases": 3},
        }}))
        os.environ["AUTOPILOT_ALERTS_POLICY"] = str(policy_path)
        config = _load_policy()
        self.assertEqual(config["large_amount_observed"]["min_dollars"], 100)
        self.assertEqual(config["shared_object_across_cases"]["min_cases"], 3)
        # Untouched defaults survive merging.
        self.assertEqual(config["hub_actor"]["min_events"],
                         DEFAULTS["hub_actor"]["min_events"])

    def test_missing_policy_file_falls_back_to_defaults(self):
        os.environ["AUTOPILOT_ALERTS_POLICY"] = "/nonexistent/alerts.json"
        self.assertEqual(_load_policy(), DEFAULTS)

    def test_corrupt_policy_file_falls_back_to_defaults(self):
        path = pathlib.Path(self._tmp.name) / "bad.json"
        path.write_text("{broken")
        os.environ["AUTOPILOT_ALERTS_POLICY"] = str(path)
        self.assertEqual(_load_policy(), DEFAULTS)

    def test_critical_sorts_before_warn_before_info(self):
        rows = [
            ("case-a", "Invoice received", ("dana",), "vendor Acme $50,000"),
            ("case-b", "Invoice received", ("dana",), "vendor Acme again"),
            *((f"case-{i}", "Issue triaged", ("dana",), f"t{i}") for i in range(5)),
        ]
        severities = [a["severity"] for a in evaluate_alerts(_log(rows))]
        order = {"critical": 0, "warn": 1, "info": 2}
        ranks = [order[s] for s in severities]
        self.assertEqual(ranks, sorted(ranks))

    def test_empty_log_has_no_alerts(self):
        self.assertEqual(evaluate_alerts(build_object_log([], [])), [])


class TestAlertsEndpoint(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "alerts.db"
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

    def test_endpoint_shape_and_count_matches_list(self):
        response = self.client.get("/api/processes/object-alerts",
                                   params={"limit": 50})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], len(body["alerts"]))
        self.assertIn("policy_source", body)
        for alert in body["alerts"]:
            self.assertIn(alert["severity"], {"critical", "warn", "info"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
