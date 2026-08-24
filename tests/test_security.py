"""Security hardening tests.

Covers what changed in the best-in-class pass: constant-time webhook token
comparison, strict signed-webhook mode, CORS origin override, and the
simulation rate limiter.
"""

import hashlib
import hmac
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio

from fastapi.testclient import TestClient


class HardeningTestCase(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "test.db"
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

    def _signed_post(self, path: str, body: bytes, secret: str = "app-secret"):
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(
            path, content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})


class TestStrictWebhookMode(HardeningTestCase):
    def tearDown(self):
        os.environ.pop("AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS", None)
        super().tearDown()

    def test_unsigned_payload_rejected_in_strict_mode_without_secret(self):
        os.environ["AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS"] = "1"
        os.environ.pop("WHATSAPP_APP_SECRET", None)
        r = self.client.post("/api/channels/whatsapp/webhook",
                             content=b'{"entry": []}',
                             headers={"Content-Type": "application/json"})
        # 503 (configuration gap made loud), not 200-with-warning.
        self.assertEqual(r.status_code, 503)

    def test_signed_payload_still_accepted_in_strict_mode(self):
        os.environ["AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS"] = "1"
        os.environ["WHATSAPP_APP_SECRET"] = "app-secret"
        try:
            r = self._signed_post("/api/channels/whatsapp/webhook", b'{"entry": []}')
            self.assertEqual(r.status_code, 200)
        finally:
            os.environ.pop("WHATSAPP_APP_SECRET", None)

    def test_default_mode_removes_strict_flag(self):
        os.environ.pop("AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS", None)
        os.environ.pop("WHATSAPP_APP_SECRET", None)
        r = self.client.post("/api/channels/whatsapp/webhook",
                             content=b'{"entry": []}',
                             headers={"Content-Type": "application/json"})
        # Demo-friendly default unchanged: accepted with a startup-style warning.
        self.assertEqual(r.status_code, 200)


class TestWebhookHandshakeTimingSafeCompare(HardeningTestCase):
    def test_wrong_token_is_403_and_right_token_echoes_challenge(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secret-token"
        try:
            wrong = self.client.get("/api/channels/whatsapp/webhook",
                                    params={"hub.mode": "subscribe",
                                            "hub.verify_token": "wrong",
                                            "hub.challenge": "CHALLENGE"})
            self.assertEqual(wrong.status_code, 403)
            right = self.client.get("/api/channels/whatsapp/webhook",
                                    params={"hub.mode": "subscribe",
                                            "hub.verify_token": "secret-token",
                                            "hub.challenge": "CHALLENGE"})
            self.assertEqual(right.status_code, 200)
            self.assertEqual(right.json(), "CHALLENGE")
        finally:
            os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)


class TestRateLimiter(HardeningTestCase):
    def setUp(self):
        super().setUp()
        from backend.security import rate_limiter

        rate_limiter._hits.clear()
        self._rate_limiter = rate_limiter

    def tearDown(self):
        os.environ.pop("AUTOPILOT_RATE_LIMIT_PER_MIN", None)
        super().tearDown()

    def _first_process_id(self) -> str:
        return self.client.get("/api/processes/").json()[0]["id"]

    def test_simulation_rate_limited_when_enabled(self):
        os.environ["AUTOPILOT_RATE_LIMIT_PER_MIN"] = "2"
        pid = self._first_process_id()
        codes = [
            self.client.get(f"/api/scores/simulate/{pid}",
                            params={"runs": 100}).status_code
            for _ in range(4)
        ]
        self.assertEqual(codes[:2], [200, 200])
        self.assertEqual(codes[2], 429)

    def test_rate_limit_disabled_by_zero(self):
        os.environ["AUTOPILOT_RATE_LIMIT_PER_MIN"] = "0"
        pid = self._first_process_id()
        for _ in range(6):
            r = self.client.get(f"/api/scores/simulate/{pid}", params={"runs": 100})
            self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
