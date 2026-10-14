"""Slack approval wire-contract tests against the real app and a temporary DB.

All signatures and identities here are synthetic; no Slack account, webhook,
network request, or third-party service is used. Slack sends a form-encoded
JSON ``payload`` and signs the exact raw bytes, before any decoding:
https://docs.slack.dev/interactivity/handling-user-interaction/
https://docs.slack.dev/authentication/verifying-requests-from-slack/
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
from unittest.mock import patch
from urllib.parse import urlencode

from backend import database
from backend.models.schema import DeploymentMode
from tests.test_lifecycle import LifecycleTestCase

SECRET = "synthetic-slack-contract-test-secret"
ENDPOINT = "/api/channels/slack/interactive"
FORM = "application/x-www-form-urlencoded"
JSON = "application/json"


class TestSlackInteractionContract(LifecycleTestCase):
    def setUp(self):
        self._saved_db_path = database.DB_PATH
        self._env = patch.dict(os.environ, {
            "SLACK_SIGNING_SECRET": SECRET,
            "AUTOPILOT_API_KEY": "",
        })
        self._env.start()
        self.addCleanup(self._env.stop)
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            database.DB_PATH = self._saved_db_path

    @staticmethod
    def _interactive(agent_id):
        return {
            "type": "block_actions",
            "user": {"id": "U-SYNTHETIC", "name": "synthetic reviewer"},
            "actions": [{"action_id": "agent_approve", "value": f"approve:{agent_id}"}],
        }

    @staticmethod
    def _form(interactive):
        return urlencode({"payload": json.dumps(interactive, ensure_ascii=False)}).encode()

    @staticmethod
    def _json(interactive, *, string_payload=False):
        payload = json.dumps(interactive) if string_payload else interactive
        return json.dumps({"payload": payload}).encode()

    @staticmethod
    def _signature_headers(raw):
        timestamp = str(int(time.time()))
        digest = hmac.new(
            SECRET.encode(), f"v0:{timestamp}:".encode() + raw, hashlib.sha256,
        ).hexdigest()
        return {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": f"v0={digest}"}

    def _post(self, raw, content_type=FORM, *, signed_raw=None, headers=None):
        request_headers = self._signature_headers(raw if signed_raw is None else signed_raw)
        if content_type is not None:
            request_headers["Content-Type"] = content_type
        if headers:
            request_headers.update(headers)
        return self.client.post(ENDPOINT, content=raw, headers=request_headers)

    def _detail(self, agent_id):
        response = self.client.get(f"/api/agents/{agent_id}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _assert_rejected_unchanged(self, agent_id, raw, content_type=FORM, *, status=422, **kwargs):
        before = self._detail(agent_id)
        response = self._post(raw, content_type, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self._detail(agent_id), before, "rejected request changed persisted state or audit")
        return response

    def test_standard_signed_form_approves_safe_draft_and_assisted_agents(self):
        for mode in (DeploymentMode.DRAFT, DeploymentMode.ASSISTED):
            with self.subTest(mode=mode):
                agent = self._deploy(f"Synthetic {mode.value} Slack approval")
                record = asyncio.run(database.get_agent(agent["id"]))
                record.config.mode = mode
                asyncio.run(database.save_agent(record))
                response = self._post(self._form(self._interactive(agent["id"])))
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), {
                    "status": "approved", "agent_id": agent["id"], "actor": "slack:U-SYNTHETIC",
                })
                detail = self._detail(agent["id"])
                self.assertEqual(detail["status"], "running")
                self.assertEqual(detail["metrics"]["approved_by"], "slack:U-SYNTHETIC")
                approvals = [entry for entry in detail["metrics"]["audit"] if entry["action"] == "approve"]
                self.assertEqual(len(approvals), 1)
                self.assertEqual(approvals[0]["actor"], "slack:U-SYNTHETIC")
                self.assertEqual(approvals[0]["from_status"], "pending_approval")
                self.assertTrue(approvals[0]["at"])
                self.assertTrue(detail["metrics"]["approved_at"])

    def test_form_decodes_unicode_plus_percent_and_spaces_exactly_once(self):
        agent = self._deploy()
        interactive = self._interactive(agent["id"])
        name = "Zoë + 李 100% %2B & equals=plus+"
        interactive["user"] = {"name": name}
        raw = self._form(interactive)
        self.assertIn(b"%2B", raw)
        self.assertIn(b"%252B", raw)
        self.assertIn(b"+", raw)
        response = self._post(raw, "application/x-www-form-urlencoded; charset=utf-8")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["actor"], f"slack:{name}")
        self.assertEqual(self._detail(agent["id"])["metrics"]["approved_by"], f"slack:{name}")

    def test_json_envelope_compatibility_with_object_or_string_and_no_content_type(self):
        for content_type in (JSON, "application/json; charset=utf-8", None):
            for string_payload in (False, True):
                with self.subTest(content_type=content_type, string_payload=string_payload):
                    agent = self._deploy()
                    interactive = self._interactive(agent["id"])
                    interactive["user"] = {"name": "legacy.reviewer"}
                    response = self._post(self._json(interactive, string_payload=string_payload), content_type)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["actor"], "slack:legacy.reviewer")
                    self.assertEqual(self._detail(agent["id"])["status"], "running")

    def test_actor_prefers_id_then_name_then_explicit_anonymous_fallback(self):
        cases = [
            ({"id": "U-123", "name": "mutable.name"}, "U-123"),
            ({"id": "U-123"}, "U-123"),
            ({"id": "", "name": "legacy.name"}, "legacy.name"),
            ({"id": "   ", "name": " legacy.name "}, "legacy.name"),
            ({"id": " U-123 ", "name": "mutable.name"}, "U-123"),
            ({"id": "   ", "name": "   "}, "anonymous"),
            ({"name": "legacy.name"}, "legacy.name"),
            ({"id": "", "name": ""}, "anonymous"),
            ({}, "anonymous"),
            (None, "anonymous"),
        ]
        for user, actor in cases:
            with self.subTest(user=user):
                agent = self._deploy()
                interactive = self._interactive(agent["id"])
                if user is None:
                    interactive.pop("user")
                else:
                    interactive["user"] = user
                response = self._post(self._form(interactive))
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["actor"], f"slack:{actor}")
                self.assertEqual(self._detail(agent["id"])["metrics"]["approved_by"], f"slack:{actor}")

    def test_missing_and_tampered_signatures_never_mutate_agent(self):
        agent = self._deploy()
        raw = self._form(self._interactive(agent["id"]))
        for headers in (
            {"X-Slack-Signature": ""},
            {"X-Slack-Request-Timestamp": ""},
            {"X-Slack-Signature": "v0=" + "0" * 64},
        ):
            with self.subTest(headers=headers):
                self._assert_rejected_unchanged(agent["id"], raw, status=403, headers=headers)
        # These forms decode identically, but signature verification must use
        # the received bytes rather than a reserialized or decoded payload.
        changed_raw = raw.replace(b"+", b"%20")
        self.assertNotEqual(raw, changed_raw)
        self._assert_rejected_unchanged(agent["id"], changed_raw, status=403, signed_raw=raw)
        before = self._detail(agent["id"])
        unsigned = self.client.post(ENDPOINT, content=raw, headers={"Content-Type": FORM})
        self.assertEqual(unsigned.status_code, 403)
        self.assertEqual(self._detail(agent["id"]), before)

    def test_signature_verification_precedes_decoding_and_content_type_dispatch(self):
        agent = self._deploy()
        for raw, content_type in (
            (b"\xff", FORM),
            (b"payload=%FF", FORM),
            (b"{not-json", JSON),
            (b"{not-json", "text/plain"),
        ):
            with self.subTest(raw=raw, content_type=content_type):
                self._assert_rejected_unchanged(
                    agent["id"], raw, content_type, status=403, signed_raw=b"different bytes",
                )

    def test_unsupported_content_types_are_415_without_mutation(self):
        agent = self._deploy()
        for content_type in ("text/plain", "multipart/form-data; boundary=synthetic", "application/xml"):
            with self.subTest(content_type=content_type):
                self._assert_rejected_unchanged(
                    agent["id"], self._json(self._interactive(agent["id"])), content_type, status=415,
                )

    def test_malformed_outer_json_and_envelope_types_are_422(self):
        agent = self._deploy()
        invalid = [b"", b"\xff", b"{broken", b"[]", b"null", b"true", b"3", b'"text"', b"{}"]
        invalid.extend(json.dumps({"payload": value}).encode() for value in (None, False, 3, [], "{bad", ""))
        for raw in invalid:
            with self.subTest(raw=raw):
                self._assert_rejected_unchanged(agent["id"], raw, JSON)

    def test_malformed_form_fields_encoding_and_inner_json_are_422(self):
        agent = self._deploy()
        invalid = [
            b"", b"\xff", b"other=value", b"payload", b"payload=", b"payload=%", b"payload=%GG",
            b"payload=%FF", b"payload=%7Bbroken", b"payload=%7B%7D&broken",
        ]
        for raw in invalid:
            with self.subTest(raw=raw):
                self._assert_rejected_unchanged(agent["id"], raw)
        for inner in ("null", "true", "42", '"text"', "[]"):
            for content_type, raw in (
                (FORM, urlencode({"payload": inner}).encode()),
                (JSON, json.dumps({"payload": inner}).encode()),
            ):
                with self.subTest(inner=inner, content_type=content_type):
                    self._assert_rejected_unchanged(agent["id"], raw, content_type)

    def test_optional_interaction_type_accepts_only_block_actions(self):
        agent = self._deploy()
        for interaction_type in (None, False, 1, [], {}, "", "view_submission", "message_action"):
            with self.subTest(interaction_type=interaction_type):
                interactive = self._interactive(agent["id"])
                interactive["type"] = interaction_type
                self._assert_rejected_unchanged(agent["id"], self._form(interactive))
        interactive = self._interactive(agent["id"])
        interactive.pop("type")
        response = self._post(self._form(interactive))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._detail(agent["id"])["status"], "running")

    def test_actions_must_contain_exactly_one_supported_object(self):
        agent = self._deploy()
        valid_action = self._interactive(agent["id"])["actions"][0]
        invalid = [None, False, "actions", {}, 1, [], [None], [False], ["action"], [[]], [{}],
                   [valid_action, valid_action], [valid_action, {"action_id": "unsupported"}]]
        for actions in invalid:
            with self.subTest(actions=actions):
                interactive = self._interactive(agent["id"])
                interactive["actions"] = actions
                self._assert_rejected_unchanged(agent["id"], self._form(interactive))
        interactive = self._interactive(agent["id"])
        interactive.pop("actions")
        self._assert_rejected_unchanged(agent["id"], self._form(interactive))

    def test_action_id_and_value_must_be_supported_strings(self):
        agent = self._deploy()
        for field, values in (
            ("action_id", [None, False, 1, [], {}, "", "unsupported"]),
            ("value", [None, False, 1, [], {}, "", "deny:agent", "approve:", "approve:   "]),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    interactive = self._interactive(agent["id"])
                    interactive["actions"][0][field] = value
                    self._assert_rejected_unchanged(agent["id"], self._form(interactive))
            interactive = self._interactive(agent["id"])
            interactive["actions"][0].pop(field)
            self._assert_rejected_unchanged(agent["id"], self._form(interactive))

    def test_provided_user_and_identity_fields_must_have_valid_types(self):
        agent = self._deploy()
        for user in (None, False, 1, "reviewer", []):
            with self.subTest(user=user):
                interactive = self._interactive(agent["id"])
                interactive["user"] = user
                self._assert_rejected_unchanged(agent["id"], self._form(interactive))
        for field in ("id", "name"):
            for value in (None, False, 1, [], {}):
                with self.subTest(field=field, value=value):
                    interactive = self._interactive(agent["id"])
                    interactive["user"][field] = value
                    self._assert_rejected_unchanged(agent["id"], self._form(interactive))

    def test_duplicate_form_payload_fields_are_rejected(self):
        agent = self._deploy()
        raw = self._form(self._interactive(agent["id"]))
        for duplicate in (raw, b"payload=", raw.replace(b"payload=", b"%70ayload=", 1)):
            with self.subTest(duplicate=duplicate):
                self._assert_rejected_unchanged(agent["id"], raw + b"&" + duplicate)
        self._assert_rejected_unchanged(agent["id"], raw + b"&context=first&context=second")

    def test_duplicate_json_keys_in_outer_and_nested_objects_are_rejected(self):
        agent = self._deploy()
        inner = json.dumps(self._interactive(agent["id"]))
        outer_duplicates = (
            '{"payload":' + inner + ',"payload":' + inner + '}',
            '{"payload":' + inner + ',"\\u0070ayload":' + inner + '}',
        )
        for outer in outer_duplicates:
            with self.subTest(outer=outer):
                self._assert_rejected_unchanged(agent["id"], outer.encode(), JSON)
        duplicates = (
            inner.replace('"actions":', '"actions": [], "actions":', 1),
            inner.replace('"id": "U-SYNTHETIC"', '"id": "ignored", "id": "U-SYNTHETIC"', 1),
            inner.replace('"action_id": "agent_approve"',
                          '"action_id": "unsupported", "action_id": "agent_approve"', 1),
            inner.replace('"value":', '"value": "deny:ignored", "value":', 1),
        )
        for duplicate in duplicates:
            for content_type, raw in (
                (FORM, urlencode({"payload": duplicate}).encode()),
                (JSON, json.dumps({"payload": duplicate}).encode()),
                (JSON, ('{"payload":' + duplicate + '}').encode()),
            ):
                with self.subTest(duplicate=duplicate, content_type=content_type, raw=raw):
                    self._assert_rejected_unchanged(agent["id"], raw, content_type)

    def test_unsafe_configs_get_same_rejection_as_rest_without_state_or_audit_changes(self):
        for mode, approval_required in (
            (DeploymentMode.DRAFT, False),
            (DeploymentMode.ASSISTED, False),
            (DeploymentMode.AUTONOMOUS, True),
        ):
            for content_type in (FORM, JSON):
                with self.subTest(mode=mode, approval_required=approval_required, content_type=content_type):
                    agent = self._deploy()
                    record = asyncio.run(database.get_agent(agent["id"]))
                    record.config.mode = mode
                    record.config.approval_required = approval_required
                    asyncio.run(database.save_agent(record))
                    before = self._detail(agent["id"])
                    rest = self.client.post(f"/api/agents/{agent['id']}/approve")
                    self.assertEqual(rest.status_code, 422, rest.text)
                    self.assertEqual(self._detail(agent["id"]), before)
                    interactive = self._interactive(agent["id"])
                    raw = self._form(interactive) if content_type == FORM else self._json(interactive)
                    slack = self._assert_rejected_unchanged(agent["id"], raw, content_type)
                    self.assertEqual(slack.json(), rest.json())

    def test_repeated_approval_conflicts_without_duplicate_audit_entry(self):
        agent = self._deploy()
        raw = self._form(self._interactive(agent["id"]))
        first = self._post(raw)
        self.assertEqual(first.status_code, 200, first.text)
        self._assert_rejected_unchanged(agent["id"], raw, status=409)
        approvals = [entry for entry in self._detail(agent["id"])["metrics"]["audit"]
                     if entry["action"] == "approve"]
        self.assertEqual(len(approvals), 1)

    def test_unknown_agent_is_404_without_mutating_existing_agent(self):
        agent = self._deploy()
        self._assert_rejected_unchanged(
            agent["id"], self._form(self._interactive("synthetic-agent-does-not-exist")), status=404,
        )
