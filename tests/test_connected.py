"""v0.7.0 Connected: connector profiles, A2A cards, Slack approvals, email sync."""

import asyncio
import json
import os
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.deployment.connectors import (  # noqa: E402
    PROFILES,
    UnknownConnectorProfile,
    build_connector_context,
    dispatch_connector_step,
)


class TestConnectorProfiles(unittest.TestCase):
    def setUp(self):
        # Isolated guard store: idempotency replays must never leak across runs.
        self._tmp = tempfile.TemporaryDirectory()
        from backend.deployment import execution_guards as guards

        guards.close_guards()
        guards._connection = None
        os.environ["AUTOPILOT_GUARD_DB"] = str(
            pathlib.Path(self._tmp.name) / "guards.db")

    def tearDown(self):
        from backend.deployment import execution_guards as guards

        guards.close_guards()
        os.environ.pop("AUTOPILOT_GUARD_DB", None)
        self._tmp.cleanup()

    def test_all_profiles_map_to_internal_tier(self):
        from backend.models.schema import StepActionType

        for name, profile in PROFILES.items():
            self.assertIs(profile["risk_tier"], StepActionType.INTERNAL_ACTION,
                          name)
            self.assertIn("credential_env", profile)
            self.assertTrue(profile["default_path"].startswith("/"))

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(UnknownConnectorProfile):
            build_connector_context("notion", "https://x", "s")

    def test_context_builders_shape_payload_per_system(self):
        sn = build_connector_context(
            "servicenow", "https://acme.service-now.com/", "Printer down",
            {"description": "3rd floor printer offline"})
        self.assertEqual(sn["webhook_url"],
                         "https://acme.service-now.com/api/now/table/incident")
        self.assertEqual(sn["payload"]["short_description"], "Printer down")
        self.assertEqual(sn["credential_env"], "SERVICENOW_TOKEN")

        sf = build_connector_context(
            "salesforce", "https://acme.my.salesforce.com", "Renewal risk")
        self.assertEqual(sf["payload"]["Subject"], "Renewal risk")

        jira = build_connector_context(
            "jira", "https://acme.atlassian.net", "Bug: login loop",
            {"fields": {"issuetype": {"name": "Bug"}}})
        self.assertEqual(jira["payload"]["fields"]["summary"], "Bug: login loop")
        self.assertIn("issuetype", jira["payload"]["fields"])

    def test_dispatch_uses_guarded_adapter_path(self):
        import httpx as httpx_mod

        captured = {}
        RealClient = httpx_mod.Client

        class FakeClient:
            def __init__(self, **_kw):
                self._client = RealClient(transport=httpx_mod.MockTransport(
                    lambda request: (
                        captured.update(url=str(request.url),
                                        auth=request.headers.get("Authorization")),
                        httpx_mod.Response(200))[1]))

            def __enter__(self):
                return self._client

            def __exit__(self, *a):
                self._client.close()
                return False

        with mock.patch("backend.deployment.tool_adapters.httpx.Client",
                        FakeClient):
            result = dispatch_connector_step(
                "Specialist assigned", "servicenow",
                "https://acme.service-now.com", "Escalation opened",
                agent_id="agent-c1", idempotency_key="conn-1")
        self.assertTrue(result["accepted"])
        self.assertEqual(captured["url"],
                         "https://acme.service-now.com/api/now/table/incident")

        replay = dispatch_connector_step(
            "Specialist assigned", "servicenow",
            "https://acme.service-now.com", "Escalation opened",
            idempotency_key="conn-1")
        self.assertEqual(replay["status"], "replayed")


class TestAgentCardEndpoint(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "card.db"
        os.environ.pop("AUTOPILOT_API_KEY", None)
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

    def _deploy_first(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps in demo data")
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Card Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]}})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_card_describes_skills_and_safety(self):
        agent = self._deploy_first()
        card = self.client.get(f"/api/agents/{agent['id']}/agent-card").json()
        self.assertEqual(card["name"], "Card Copilot")
        self.assertTrue(card["capabilities"]["humanApproval"])
        self.assertGreaterEqual(len(card["skills"]), 1)
        self.assertIn("step-0", {s["id"] for s in card["skills"]})
        self.assertEqual(card["securitySchemes"]["dashboardKey"]["name"],
                         "X-API-Key")

    def test_card_404_for_missing_agent(self):
        self.assertEqual(
            self.client.get("/api/agents/agent-missing/agent-card").status_code,
            404)


class TestSlackInteractiveApprovals(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "slack.db"
        self._saved = {k: os.environ.get(k) for k in ("SLACK_SIGNING_SECRET",
                                                      "AUTOPILOT_API_KEY")}
        for k in self._saved:
            os.environ.pop(k, None)
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
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _deploy_pending(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        if not score["eligible_steps"]:
            self.skipTest("no eligible steps")
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Slack Approve Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]}})
        return response.json()

    @staticmethod
    def _interactive(agent_id):
        return json.dumps({"payload": json.dumps({
            "user": {"name": "dana.csm"},
            "actions": [{"action_id": "agent_approve",
                         "value": f"approve:{agent_id}"}],
        })}).encode()

    def test_button_approval_routes_through_guarded_transition(self):
        agent = self._deploy_pending()
        response = self.client.post(
            "/api/channels/slack/interactive",
            content=self._interactive(agent["id"]),
            headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["actor"], "slack:dana.csm")

        detail = self.client.get(f"/api/agents/{agent['id']}").json()
        self.assertEqual(detail["status"], "running")
        actors = [e["actor"] for e in detail["metrics"]["audit"]]
        self.assertIn("slack:dana.csm", actors)

    def test_double_approval_conflicts_and_bad_action_422(self):
        agent = self._deploy_pending()
        first = self.client.post("/api/channels/slack/interactive",
                                 content=self._interactive(agent["id"]))
        self.assertEqual(first.status_code, 200)
        again = self.client.post("/api/channels/slack/interactive",
                                 content=self._interactive(agent["id"]))
        self.assertEqual(again.status_code, 409)

        wrong = self.client.post("/api/channels/slack/interactive", content=json.dumps({
            "payload": json.dumps({"actions": [{"action_id": "nope", "value": "x"}]})}))
        self.assertEqual(wrong.status_code, 422)

    def test_signature_enforced_when_secret_configured(self):
        os.environ["SLACK_SIGNING_SECRET"] = "s3cret"
        agent = self._deploy_pending()
        unsigned = self.client.post("/api/channels/slack/interactive",
                                    content=self._interactive(agent["id"]))
        self.assertEqual(unsigned.status_code, 403)


class TestEmailSync(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        import backend.database as database

        database.DB_PATH = pathlib.Path(self._tmp.name) / "email.db"
        self._saved = {k: os.environ.get(k) for k in (
            "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        asyncio.run(__import__("backend.database", fromlist=["close_db"]).close_db())
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def test_parse_email_message_extracts_body_and_thread(self):
        from backend.ingestion.email_connector import parse_email_message

        raw = (b"From: Dana <dana@corp.example>\r\n"
               b"Subject: Invoice exception received\r\n"
               b"To: ops@corp.example\r\n"
               b"Message-ID: <abc123@corp>\r\n"
               b"Date: Mon, 24 Aug 2026 10:00:00 +0000\r\n"
               b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
               b"Invoice exception received for vendor Acme.\r\n")
        message = parse_email_message(raw, "email:ops@corp.example")
        self.assertIsNotNone(message)
        self.assertEqual(message.id, "email:<abc123@corp>")
        self.assertTrue(message.content.startswith("Re: Invoice exception"))
        self.assertIn("vendor Acme", message.content)
        self.assertEqual(message.metadata["read_only"], True)

    def test_parse_email_message_survives_ml_enrichment_failure(self):
        from backend.ingestion.email_connector import parse_email_message

        raw = (b"From: Dana <dana@corp.example>\r\n"
               b"Subject: Classifier outage\r\n"
               b"To: ops@corp.example\r\n"
               b"Message-ID: <mlfail@corp>\r\n\r\n"
               b"Body must still parse when classification fails.\r\n")
        with mock.patch(
            "backend.ml.email_classifier.EmailClassifier.predict",
            side_effect=RuntimeError("classifier offline"),
        ):
            message = parse_email_message(raw, "email:ops@corp.example")
        self.assertIsNotNone(message)
        self.assertNotIn("ml_intent", message.metadata)

    def test_sync_without_credentials_is_configuration_error(self):
        from backend.ingestion.email_connector import (
            EmailConfigurationError,
            fetch_recent_messages,
        )

        with self.assertRaises(EmailConfigurationError):
            fetch_recent_messages()


class TestEmailSyncDeep(unittest.TestCase):
    """IMAP flow, header decoding, multipart parsing, and the API route."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        import backend.database as database

        self._db = database
        database.DB_PATH = pathlib.Path(self._tmp.name) / "email2.db"
        self._saved = {k: os.environ.get(k) for k in (
            "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
            "SLACK_SIGNING_SECRET")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        asyncio.run(self._db.close_db())
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def test_credentials_require_all_three_and_default_folder(self):
        from backend.ingestion.email_connector import (
            EmailConfigurationError,
            _credentials,
        )

        os.environ.update(IMAP_HOST="imap.corp", IMAP_USER="ops",
                          IMAP_PASSWORD="pw", IMAP_FOLDER="")
        host, user, password, folder = _credentials()
        self.assertEqual((host, user, password, folder),
                         ("imap.corp", "ops", "pw", "INBOX"))
        os.environ.pop("IMAP_PASSWORD")
        with self.assertRaises(EmailConfigurationError):
            _credentials()

    def test_decode_header_handles_encoded_words(self):
        from backend.ingestion.email_connector import _decode_header

        self.assertEqual(
            _decode_header("=?utf-8?b?SW52b2ljZQ==?="), "Invoice")
        self.assertEqual(_decode_header(None), "unknown")

    def test_multipart_and_truncation_paths(self):
        from backend.ingestion.email_connector import parse_email_message

        raw = (b"From: dana@corp\r\nSubject: multipart\r\n"
               b"Message-ID: <mp@corp>\r\n"
               b'Content-Type: multipart/mixed; boundary="BB"\r\n\r\n'
               b"--BB\r\nContent-Type: text/plain\r\n\r\nbody text here\r\n"
               b"--BB\r\nContent-Type: application/pdf\r\n\r\nBIN\r\n--BB--\r\n")
        message = parse_email_message(raw, "email:x")
        self.assertIn("body text here", message.content)

        no_date = (b"From: d@corp\r\nSubject: nodate\r\n\r\nhello\r\n")
        message2 = parse_email_message(no_date, "email:x")
        self.assertIsNotNone(message2.timestamp.tzinfo)

        huge_body = b"x" * 9000
        long_raw = (b"From: d@corp\r\nSubject: big\r\n\r\n" + huge_body)
        message3 = parse_email_message(long_raw, "email:x")
        self.assertLessEqual(len(message3.content), 8000)

    def test_fetch_recent_messages_with_fake_imap(self):
        from backend.ingestion import email_connector as ec

        raw_email = (b"From: dana@corp\r\nSubject: Renewal risk alerted\r\n"
                     b"Message-ID: <rr@corp>\r\n\r\nAcme renewal risk.\r\n")

        class FakeConn:
            def __init__(self, *a, **kw):
                pass

            def login(self, user, password):
                pass

            def select(self, folder, readonly=False):
                return ("OK", [b"1"])

            def search(self, *a):
                return ("OK", [b"1"])

            def fetch(self, uid, spec):
                return ("OK", [(b"1 (RFC822 {n}", raw_email), b")"])

            def logout(self):
                pass

        with mock.patch("imaplib.IMAP4_SSL", FakeConn), \
             mock.patch.dict(os.environ, {
                 "IMAP_HOST": "imap", "IMAP_USER": "ops",
                 "IMAP_PASSWORD": "pw"}):
            messages = ec.fetch_recent_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].channel_id, "email:ops")
        self.assertIn("Renewal risk", messages[0].content)

    def test_sync_email_messages_upserts_channel_and_messages(self):
        from unittest.mock import patch

        from backend import database
        from backend.ingestion.email_connector import sync_email_messages

        asyncio.run(database.init_db())
        fake = __import__("backend.models.schema", fromlist=["Message"]).Message(
            id="email:<x@y>", channel_id="email:ops@corp",
            sender="dana", content="Contract received for review from Acme",
            timestamp=datetime.now(UTC))
        with patch("backend.ingestion.email_connector.fetch_recent_messages",
                   return_value=[fake]):
            messages = asyncio.run(sync_email_messages())
        self.assertEqual(len(messages), 1)
        channels = asyncio.run(database.get_channels())
        self.assertIn("email:ops@corp", {c.id for c in channels})

    def test_email_sync_endpoint_503_without_credentials_then_happy(self):
        from fastapi.testclient import TestClient

        import backend.main as main_mod

        with TestClient(main_mod.app) as client:
            missing = client.post("/api/channels/email/sync",
                                  headers={"X-API-Key": ""})
            self.assertEqual(missing.status_code, 503)

            fake = __import__("backend.models.schema", fromlist=["Message"]).Message(
                id="email:<z@z>", channel_id="email:ops2",
                sender="dana", content="Issue triaged for Acme",
                timestamp=datetime.now(UTC))
            from unittest.mock import patch


            with patch("backend.ingestion.email_connector.sync_email_messages",
                       return_value=[fake]):
                ok = client.post("/api/channels/email/sync")
            self.assertEqual(ok.status_code, 200, ok.text)
            self.assertEqual(ok.json()["messages_seen"], 1)


class TestSlackInteractiveBranches(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "slackb.db"
        self.client = __import__("fastapi.testclient",
                                 fromlist=["TestClient"]).TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    def post(self, content: bytes):
        return self.client.post("/api/channels/slack/interactive",
                                content=content,
                                headers={"Content-Type": "application/json"})

    def test_malformed_outer_json_is_422(self):
        self.assertEqual(self.post(b"{oops").status_code, 422)

    def test_nested_payload_not_dict_is_422(self):
        response = self.post(json.dumps({"payload": "[1,2]"}).encode())
        self.assertEqual(response.status_code, 422)

    def test_no_actions_is_422(self):
        response = self.post(json.dumps({"payload": "{}"}).encode())
        self.assertEqual(response.status_code, 422)


class TestSlackSignatureMismatch(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "slacksig.db"
        self.client = __import__("fastapi.testclient",
                                 fromlist=["TestClient"]).TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    def test_wrong_signature_value_rejected(self):
        old = os.environ.get("SLACK_SIGNING_SECRET")
        os.environ["SLACK_SIGNING_SECRET"] = "s3cret"
        try:
            response = self.client.post(
                "/api/channels/slack/interactive",
                content=b"{}",
                headers={"X-Slack-Request-Timestamp": "123",
                         "X-Slack-Signature": "v0=" + "0" * 64})
            self.assertEqual(response.status_code, 403)
        finally:
            if old is None:
                os.environ.pop("SLACK_SIGNING_SECRET", None)
            else:
                os.environ["SLACK_SIGNING_SECRET"] = old



if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestFinalCoverageGaps(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "gaps.db"
        self.client = __import__("fastapi.testclient",
                                 fromlist=["TestClient"]).TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    def _deploy_pending(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        response = self.client.post("/api/agents/deploy", json={
            "process_id": process["id"], "name": "Gap Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]}})
        return response.json()

    @staticmethod
    def _interactive(value, action_id="agent_approve"):
        return json.dumps({"payload": json.dumps({
            "user": {"name": "eve"},
            "actions": [{"action_id": action_id, "value": value}]})}).encode()

    def test_slack_inner_malformed_json_is_422(self):
        response = self.post_helper(json.dumps({"payload": "{bad"}).encode())
        self.assertEqual(response.status_code, 422)

    def post_helper(self, content):
        return self.client.post("/api/channels/slack/interactive",
                                content=content)

    def test_slack_bad_value_and_missing_agent_422_404(self):
        self.assertEqual(
            self.post_helper(self._interactive("deny:x")).status_code, 422)
        self.assertEqual(
            self.post_helper(self._interactive("approve:agent-missing")).status_code,
            404)

    def test_slack_corrupt_audit_repaired_on_button_approve(self):
        agent = self._deploy_pending()
        raw = asyncio.run(self._db.get_agent(agent["id"]))
        raw.metrics["audit"] = "corrupted"
        asyncio.run(self._db.save_agent(raw))
        ok = self.post_helper(self._interactive(f"approve:{raw.id}"))
        self.assertEqual(ok.status_code, 200)
        repaired = asyncio.run(self._db.get_agent(raw.id))
        self.assertIsInstance(repaired.metrics["audit"], list)
        self.assertEqual(repaired.metrics["audit"][0]["actor"], "slack:eve")

    def test_upsert_message_channel_existing_and_unknown_kind(self):
        import backend.database as db

        asyncio.run(db.init_db())
        first = asyncio.run(db.upsert_message_channel("email:ops"))
        again = asyncio.run(db.upsert_message_channel("email:ops"))  # existing branch
        weird = asyncio.run(db.upsert_message_channel("pigeon:rooftop"))
        self.assertEqual(first.id, again.id)
        self.assertEqual(weird.type.value, "email")

    def test_generic_payload_builder_direct(self):
        from backend.deployment.connectors import _generic_payload

        self.assertEqual(_generic_payload("s", {"k": 1}),
                         {"summary": "s", "k": 1})

    def test_email_search_fail_and_fetch_fail_and_logout_raise(self):
        from backend.ingestion import email_connector as ec

        os.environ.update(IMAP_HOST="i", IMAP_USER="u",
                          IMAP_PASSWORD="p", IMAP_FOLDER="")

        class Conn:
            calls = {"logout": 0}

            def login(self, *a):
                pass

            def select(self, folder, readonly=False):
                return ("NO", [])

            def search(self, *a):  # first variant fails here
                return ("NO", [])

            def fetch(self, uid, spec):
                return ("NO", None)  # second variant fails here


            def logout(self):
                Conn.calls["logout"] += 1
                raise RuntimeError("bye")  # third: best-effort logout

        c1 = Conn()
        c2 = Conn()
        with mock.patch("imaplib.IMAP4_SSL", lambda *a, **k: c1):
            self.assertEqual(ec.fetch_recent_messages(), [])
        c2.select = lambda folder, readonly=False: ("OK", [b"7"])
        c2.search = lambda *a: ("OK", [b"7"])
        with mock.patch("imaplib.IMAP4_SSL", lambda *a, **k: c2):
            self.assertEqual(ec.fetch_recent_messages(), [])  # fetch NO skipped

    def test_sync_email_messages_empty_returns_early(self):
        from unittest.mock import patch

        from backend.ingestion.email_connector import sync_email_messages

        with patch("backend.ingestion.email_connector.fetch_recent_messages",
                   return_value=[]):
            self.assertEqual(asyncio.run(sync_email_messages()), [])


class TestEmailTimestampFallbacks(unittest.TestCase):
    def test_invalid_and_naive_date_headers(self):
        from backend.ingestion.email_connector import parse_email_message

        bad = (b"From: d@corp\r\nSubject: bad date\r\n"
               b"Date: definitely-not-a-date\r\n\r\nhi\r\n")
        message = parse_email_message(bad, "email:x")
        self.assertIsNotNone(message.timestamp)

        naive = (b"From: d@corp\r\nSubject: naive\r\n"
                 b"Date: Mon, 24 Aug 2026 10:00:00\r\n\r\nhi\r\n")
        message2 = parse_email_message(naive, "email:x")
        self.assertIsNotNone(message2.timestamp.tzinfo)
