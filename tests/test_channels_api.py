"""Channel API surface tests: Slack sync, WhatsApp handshake + ingestion.

Covers the HTTP paths the connectors feed: configuration errors surface as
503 (not crashes), signature verification rejects forged payloads, and
ingestion always ends in a rediscovery pass.
"""

import asyncio
import hashlib
import hmac as hmac_mod
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402


class ChannelsApiTestCase(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "channels.db"
        self._env_backup = {
            k: os.environ.get(k)
            for k in ("WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET",
                      "SLACK_BOT_TOKEN", "AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS")
        }
        for k in self._env_backup:
            os.environ.pop(k, None)
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _wa_payload(self, msg_type="text", body="Invoice exception received for vendor Acme",
                    phone="pn-1", ts=None):
        import json
        from time import time

        message = {"id": f"wa-{ts or int(time())}", "from": "+15550001",
                   "timestamp": str(ts or int(time())), "type": msg_type}
        if msg_type == "text":
            message["text"] = {"body": body}
        return json.dumps({
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": phone},
                "messages": [message],
            }}]}],
        }).encode()


class TestChannelReads(ChannelsApiTestCase):
    def test_list_and_get_channels_with_404(self):
        listed = self.client.get("/api/channels/")
        self.assertEqual(listed.status_code, 200)
        channel_id = listed.json()[0]["id"]
        found = self.client.get(f"/api/channels/{channel_id}")
        self.assertEqual(found.status_code, 200)
        missing = self.client.get("/api/channels/does-not-exist")
        self.assertEqual(missing.status_code, 404)


class TestSlackSync(ChannelsApiTestCase):
    def test_sync_without_token_is_503(self):
        response = self.client.post("/api/channels/slack/sync", json={
            "slack_channel_id": "C123", "display_name": "Support"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("SLACK_BOT_TOKEN", response.json()["detail"])

    def test_sync_success_ingests_and_rediscovers(self):
        from backend.models.schema import Message

        async def fake_sync(slack_channel_id, channel_id):
            return [Message(
                id=f"slack:{slack_channel_id}:1", channel_id=channel_id,
                sender="dana", content="Renewal risk alerted for Acme",
                timestamp=__import__("datetime").datetime.now(
                    __import__("datetime").UTC),
            )]

        import backend.api.channels as channels_mod

        orig = channels_mod.sync_channel
        channels_mod.sync_channel = fake_sync
        try:
            response = self.client.post("/api/channels/slack/sync", json={
                "slack_channel_id": "C123", "display_name": "Support"})
        finally:
            channels_mod.sync_channel = orig
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["messages_seen"], 1)
        self.assertGreaterEqual(body["processes"], 0)


class TestWhatsAppHandshake(ChannelsApiTestCase):
    def test_handshake_disabled_without_token(self):
        response = self.client.get(
            "/api/channels/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"},
        )
        self.assertEqual(response.status_code, 503)

    def test_handshake_rejects_wrong_token(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secret-token"
        response = self.client.get(
            "/api/channels/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                    "hub.challenge": "42"},
        )
        self.assertEqual(response.status_code, 403)

    def test_handshake_echoes_challenge_on_match(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secret-token"
        response = self.client.get(
            "/api/channels/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "secret-token",
                    "hub.challenge": "424242"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), "424242")


class TestWhatsAppIngestion(ChannelsApiTestCase):
    def post_webhook(self, raw: bytes, signature: str | None = None):
        headers = {}
        if signature is not None:
            headers["X-Hub-Signature-256"] = signature
        return self.client.post("/api/channels/whatsapp/webhook",
                                content=raw, headers=headers)

    def test_malformed_json_is_422(self):
        response = self.post_webhook(b"{not json")
        self.assertEqual(response.status_code, 422)

    def test_empty_payload_reports_zero(self):
        response = self.post_webhook(b"{}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages_seen"], 0)

    def test_text_message_ingests_and_discovers(self):
        response = self.post_webhook(self._wa_payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["messages_seen"], 1)

    def test_media_type_gets_placeholder_content(self):
        response = self.post_webhook(self._wa_payload(msg_type="image"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages_seen"], 1)

    def test_phone_filter_excludes_foreign_numbers(self):
        os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "pn-mine"
        try:
            response = self.post_webhook(self._wa_payload(phone="pn-other"))
            self.assertEqual(response.json()["messages_seen"], 0)
        finally:
            os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)

    def test_forged_signature_is_rejected_when_secret_configured(self):
        os.environ["WHATSAPP_APP_SECRET"] = "app-secret"
        response = self.post_webhook(self._wa_payload(), signature="sha256=" + "0" * 64)
        self.assertEqual(response.status_code, 403)

    def test_valid_signature_passes_verification(self):
        secret = "app-secret"
        os.environ["WHATSAPP_APP_SECRET"] = secret
        raw = self._wa_payload(body="Contract received for review from Acme")
        digest = hmac_mod.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        response = self.post_webhook(raw, signature=f"sha256={digest}")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["messages_seen"], 1)

    def test_signature_header_missing_prefix_is_403(self):
        os.environ["WHATSAPP_APP_SECRET"] = "app-secret"
        response = self.post_webhook(self._wa_payload(), signature="md5=nope")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
