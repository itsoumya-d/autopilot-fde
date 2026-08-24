"""v0.9.0 Object-centric discovery: extractors, OCEL-shaped log, API, CLI."""

import asyncio
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.discovery.object_centric import (  # noqa: E402
    build_object_log,
    extract_objects,
    object_trace,
)
from backend.models.schema import Activity, Message  # noqa: E402


def _activity(case="case-1", name="Invoice reconciled", actors=("dana",),
              sources=(), minute=0):
    return Activity(
        id=f"a-{case}-{name}-{minute}", name=name, category="finance",
        case_id=case, actors=list(actors),
        timestamp=datetime(2026, 8, 24, 10, minute, tzinfo=UTC),
        source_messages=list(sources), confidence=0.9,
    )


def _message(mid="m-1", content="hello", sender="dana", metadata=None):
    return Message(id=mid, channel_id="ch-1", sender=sender, content=content,
                   timestamp=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                   metadata=metadata or {})


class TestExtractors(unittest.TestCase):
    def test_case_and_actors_always_present(self):
        objects = extract_objects(_activity(), {})
        self.assertEqual(objects["case"], ["case:case-1"])
        self.assertEqual(objects["actor"], ["actor:dana"])

    def test_ticket_pattern_from_text(self):
        message = _message(content="Escalate INC004221 and CASE-77 please")
        objects = extract_objects(
            _activity(sources=["m-1"]), {"m-1": message})
        self.assertIn("ticket:INC004221", objects["ticket"])
        self.assertIn("ticket:CASE-77", objects["ticket"])

    def test_vendor_slug_normalization(self):
        message = _message(content="vendor Acme-Corp raised it")
        objects = extract_objects(_activity(sources=["m-1"]), {"m-1": message})
        self.assertIn("vendor:acme-corp", objects["vendor"])

    def test_amount_normalization_strips_commas(self):
        message = _message(content="$12,500.50 approved")
        objects = extract_objects(_activity(sources=["m-1"]), {"m-1": message})
        self.assertEqual(objects["amount"], ["amount:$12500.50"])

    def test_email_domains_lowercased(self):
        message = _message(content="ping Dana.Doe@Acme.Com. about it")
        objects = extract_objects(_activity(sources=["m-1"]), {"m-1": message})
        self.assertIn("domain:acme.com", objects["email-domain"])

    def test_metadata_tickets_honored(self):
        message = _message(metadata={"ticket_ids": ["T-9"]})
        objects = extract_objects(_activity(sources=["m-1"]), {"m-1": message})
        self.assertIn("ticket:T-9", objects["ticket"])

    def test_missing_source_messages_yield_case_only(self):
        objects = extract_objects(_activity(sources=["ghost"]), {})
        self.assertEqual(sorted(objects), ["actor", "case"])


class TestBuildObjectLog(unittest.TestCase):
    def fixture(self):
        m1 = _message("m-1", "Invoice reconciled for vendor Acme $1,000 (INC555)",
                      sender="dana")
        m2 = _message("m-2", "Payment approval requested from dana@corp.example",
                      sender="eve")
        activities = [
            _activity(name="Invoice exception received", sources=["m-1"], minute=0),
            _activity(name="Invoice reconciled", sources=["m-1"], minute=5),
            _activity(case="case-2", name="Payment confirmed",
                      actors=("eve",), sources=["m-2"], minute=9),
        ]
        return build_object_log(activities, [m1, m2])

    def test_ocel_shape_and_ordering(self):
        log = self.fixture()
        self.assertEqual(log["ocel_version"], "2.0-inspired")
        times = [e["time"] for e in log["events"]]
        self.assertEqual(times, sorted(times))
        types = {o["name"] for o in log["objectTypes"]}
        for expected in ("case", "actor", "vendor", "amount", "ticket",
                         "email-domain"):
            self.assertIn(expected, types)

    def test_event_relationships_are_qualified_e2o(self):
        event = next(e for e in self.fixture()["events"]
                     if e["type"] == "Payment confirmed")
        qualifiers = {r["qualifier"]: r["objectId"] for r in event["relationships"]}
        self.assertEqual(qualifiers["case"], "case:case-2")
        self.assertEqual(qualifiers["actor"], "actor:eve")

    def test_o2o_pairs_deduplicated_with_qualifiers(self):
        log = self.fixture()
        vendor_obj = next(o for o in log["objects"]
                          if o["id"] == "vendor:acme")
        related_ids = {r["objectId"] for r in vendor_obj["relationships"]}
        self.assertIn("case:case-1", related_ids)
        pair_keys = [(r["objectId"], r["qualifier"])
                     for r in vendor_obj["relationships"]]
        self.assertEqual(len(pair_keys), len(set(pair_keys)))

    def test_summaries_count_objects_and_touching_events(self):
        summaries = self.fixture()["summaries"]
        self.assertEqual(summaries["vendor"]["objects"], 1)
        self.assertEqual(summaries["vendor"]["events_touching"], 2)
        self.assertEqual(summaries["case"]["objects"], 2)

    def test_object_trace_is_chronological_slice(self):
        log = self.fixture()
        trace = object_trace(log, "vendor:acme")
        times = [e["time"] for e in trace]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(
            any(r["objectId"] == "vendor:acme" for r in e["relationships"])
            for e in trace))

    def test_empty_inputs_produce_empty_but_valid_log(self):
        log = build_object_log([], [])
        self.assertEqual(log["events"], [])
        self.assertEqual(log["objects"], [])
        self.assertEqual(log["summaries"], {})


class TestObjectLogEndpoint(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "ocel.db"
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

    def test_endpoint_returns_shaped_log(self):
        response = self.client.get("/api/processes/object-log",
                                   params={"limit": 10})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreater(len(body["events"]), 0)
        self.assertIn("case", {o["name"] for o in body["objectTypes"]})

    def test_limit_zero_yields_empty_events(self):
        response = self.client.get("/api/processes/object-log",
                                   params={"limit": 0})
        self.assertEqual(response.json()["events"], [])


class TestExportCli(unittest.TestCase):
    def test_cli_writes_deterministic_json(self):
        import subprocess

        project_root = pathlib.Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env.update(PYTHONPATH=str(project_root),
                   AUTOPILOT_DB_PATH=str(pathlib.Path(self.tmpdir.name) / "cli.db"))
        out_a = pathlib.Path(self.tmpdir.name) / "a.json"
        out_b = pathlib.Path(self.tmpdir.name) / "b.json"
        for target in (out_a, out_b):
            subprocess.run(
                [sys.executable, str(project_root / "scripts" / "export_object_log.py"),
                 "--out", str(target)], check=True, env=env,
                capture_output=True, cwd=str(project_root))
        self.assertEqual(json.loads(out_a.read_text()),
                         json.loads(out_b.read_text()))

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDuplicateObjectGuard(unittest.TestCase):
    def test_duplicate_ids_within_event_do_not_self_relate(self):
        message = _message(content="a@x.com wrote to b@x.com")
        objects = extract_objects(_activity(sources=["m-1"]), {"m-1": message})
        self.assertEqual(objects["email-domain"].count("domain:x.com"), 2)
        log = build_object_log(
            [_activity(sources=["m-1"])], [message])
        domain_obj = next(o for o in log["objects"] if o["id"] == "domain:x.com")
        self.assertNotIn("domain:x.com",
                         {r["objectId"] for r in domain_obj["relationships"]})
