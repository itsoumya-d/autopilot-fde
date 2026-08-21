"""Ingestion-connector and LLM-enhancer tests, fully mocked — no network.

These cover the three weakest spots in the backend: the Slack sync
normalization rules, the optional LLM enhancement fallback chain, and the
WhatsAppConnector live-check contract.
"""

import asyncio
import os
import pathlib
import sys
import unittest
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.ingestion.slack_connector import (  # noqa: E402
    SlackConfigurationError,
    sync_channel,
)
from backend.ingestion.whatsapp_connector import WhatsAppConnector  # noqa: E402
from backend.llm.enhancer import (  # noqa: E402
    HttpxLLMEnhancer,
    RuleBasedEnhancer,
    _extract_json,
    enhance_processes,
    get_enhancer,
)
from backend.models.schema import Process  # noqa: E402


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── LLM enhancer ───────────────────────────────────────────────────────────


class TestEnhancerFallbackChain(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("LLM_API_KEY", None)

    def test_no_key_selects_rule_based(self):
        os.environ.pop("LLM_API_KEY", None)
        self.assertIsInstance(get_enhancer(), RuleBasedEnhancer)

    def test_rule_based_summary_is_deterministic_and_complete(self):
        process = {
            "name": "Deal Desk",
            "activities": [{"name": "A"}, {"name": "B"}],
            "metrics": {"unique_actors_count": 3, "trace_count": 7},
        }
        enriched = RuleBasedEnhancer().enhance_process(process)
        self.assertIn("2-step", enriched["llm_summary"])
        self.assertIn("7 observed trace(s)", enriched["llm_summary"])
        self.assertEqual(set(enriched["step_rationale"]), {"A", "B"})
        # The input dict is never mutated.
        self.assertNotIn("llm_summary", process)

    def test_extract_json_variants(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})
        self.assertEqual(_extract_json('noise ```json\n{"b": 2}\n``` tail'), {"b": 2})
        self.assertIsNone(_extract_json("no braces here"))
        self.assertIsNone(_extract_json("{not json}"))
        self.assertIsNone(_extract_json('[1, 2]'))  # non-object JSON rejected


class _FakeResponse:
    def __init__(self, payload=None, status_error=False):
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise RuntimeError("http 500")

    def json(self):
        return self._payload


class TestHttpxLLMEnhancer(unittest.TestCase):
    def setUp(self):
        self.process = {
            "name": "Support Escalation",
            "activities": [{"name": "Triage"}],
            "metrics": {},
        }

    def test_successful_llm_reply_is_used(self):
        import httpx

        content = '{"summary": "Escalations are triaged.", "rationale": {"Triage": "read-only"}}'
        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["auth"] = kwargs["headers"]["Authorization"]
            return _FakeResponse({"choices": [{"message": {"content": content}}]})

        original = httpx.post
        httpx.post = fake_post
        try:
            enriched = HttpxLLMEnhancer("sk-test", base_url="https://llm.example/v1").enhance_process(
                self.process)
        finally:
            httpx.post = original
        self.assertEqual(enriched["llm_summary"], "Escalations are triaged.")
        self.assertEqual(enriched["step_rationale"]["Triage"], "read-only")
        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["auth"], "Bearer sk-test")

    def test_garbage_reply_falls_back_to_rules(self):
        import httpx

        def fake_post(url, **kwargs):
            return _FakeResponse({"choices": [{"message": {"content": "not json at all"}}]})

        original = httpx.post
        httpx.post = fake_post
        try:
            enriched = HttpxLLMEnhancer("k").enhance_process(self.process)
        finally:
            httpx.post = original
        self.assertIn("deterministic risk table", enriched["step_rationale"]["Triage"])

    def test_http_failure_falls_back_to_rules(self):
        import httpx

        def fake_post(url, **kwargs):
            return _FakeResponse(status_error=True)

        original = httpx.post
        httpx.post = fake_post
        try:
            enriched = HttpxLLMEnhancer("k").enhance_process(self.process)
        finally:
            httpx.post = original
        self.assertIn("llm_summary", enriched)  # rule-based summary present

    def test_non_dict_rationale_becomes_empty_dict(self):
        import httpx

        content = '{"summary": "S", "rationale": "flat"}'

        def fake_post(url, **kwargs):
            return _FakeResponse({"choices": [{"message": {"content": content}}]})

        original = httpx.post
        httpx.post = fake_post
        try:
            enriched = HttpxLLMEnhancer("k").enhance_process(self.process)
        finally:
            httpx.post = original
        self.assertEqual(enriched["step_rationale"], {})


class TestEnhanceProcessesMutation(unittest.TestCase):
    def test_descriptions_updated_in_place(self):
        os.environ.pop("LLM_API_KEY", None)  # force the deterministic path
        processes = [
            Process(id="p1", name="P One",
                    activities=[], metrics={"unique_actors_count": 1}),
        ]
        enhance_processes(processes)
        self.assertIn("0-step", processes[0].description)


# ── Slack connector ────────────────────────────────────────────────────────


class _FakeSlackClient:
    def __init__(self, history, replies=None, auth_ok=True):
        self._history = history
        self._replies = replies or {}
        self._auth_ok = auth_ok
        self.reply_calls: list[dict] = []

    async def auth_test(self):
        return {"ok": self._auth_ok}

    async def conversations_history(self, **kwargs):
        return {"messages": self._history}

    async def conversations_replies(self, **kwargs):
        self.reply_calls.append(kwargs)
        return {"messages": self._replies.get(kwargs.get("ts"), [])}


class TestSlackSync(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SLACK_BOT_TOKEN", None)

    def test_missing_token_raises_configuration_error(self):
        os.environ.pop("SLACK_BOT_TOKEN", None)
        with self.assertRaises(SlackConfigurationError):
            run(sync_channel("C123"))

    def test_failed_auth_raises_configuration_error(self):
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"
        import backend.ingestion.slack_connector as mod

        original = mod.AsyncWebClient
        mod.AsyncWebClient = lambda token: _FakeSlackClient([], auth_ok=False)
        try:
            with self.assertRaises(SlackConfigurationError):
                run(sync_channel("C123"))
        finally:
            mod.AsyncWebClient = original

    def test_sync_normalizes_skips_subtypes_and_pulls_replies(self):
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"
        import backend.ingestion.slack_connector as mod

        history = [
            {"ts": "100.0", "user": "U1", "text": "root message", "reply_count": 2},
            {"ts": "101.0", "user": "U1", "text": "duplicate coming", },
            {"ts": "101.0", "user": "U1", "text": "duplicate coming"},
            {"ts": "102.0", "user": "bot", "text": "bot message", "subtype": "bot_message"},
            {"ts": "103.0", "user": "U2", "text": "channel join", "subtype": "channel_join"},
            {"ts": "104.0", "user": "U3", "text": "real update"},
        ]
        replies = {
            "100.0": [
                {"ts": "100.0", "user": "U1", "text": "root message"},
                {"ts": "105.0", "user": "U4", "text": "thread reply"},
            ],
        }
        fake = _FakeSlackClient(history, replies)
        original = mod.AsyncWebClient
        mod.AsyncWebClient = lambda token: fake
        try:
            messages = run(sync_channel("C123", "slack:C123"))
        finally:
            mod.AsyncWebClient = original

        texts = [m.content for m in messages]
        self.assertIn("root message", texts)
        self.assertIn("thread reply", texts)
        self.assertIn("real update", texts)
        self.assertEqual(texts.count("duplicate coming"), 1)  # deduped by ts
        self.assertNotIn("bot message", texts)
        self.assertNotIn("channel join", texts)
        thread_msg = next(m for m in messages if m.content == "thread reply")
        self.assertEqual(thread_msg.thread_id, "100.0")
        self.assertTrue(all(m.metadata.get("read_only") for m in messages))
        # Replies were fetched once for the one threading root.
        self.assertEqual(len(fake.reply_calls), 1)


# ── WhatsApp live connector ────────────────────────────────────────────────


class TestWhatsAppConnector(unittest.TestCase):
    def test_missing_credentials_raise(self):
        with self.assertRaises(ValueError):
            WhatsAppConnector({})
        with self.assertRaises(ValueError):
            WhatsAppConnector({"access_token": "tok"})

    def test_fetch_messages_is_noop_by_contract(self):
        connector = WhatsAppConnector({
            "access_token": "tok", "phone_number_id": "pn", "verify_token": "vt"})
        result = run(connector.fetch_messages(datetime.now(UTC)))
        self.assertEqual(result, [])

    def test_channel_type(self):
        from backend.models.schema import ChannelType

        connector = WhatsAppConnector({
            "access_token": "tok", "phone_number_id": "pn"})
        self.assertIs(connector.channel_type, ChannelType.WHATSAPP)

    def test_connect_reports_health_from_graph_api(self):
        import httpx

        connector = WhatsAppConnector({
            "access_token": "tok", "phone_number_id": "pn"})

        class _FakeAsyncClient:
            def __init__(self, status):
                self._status = status
                self.calls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url, headers=None):
                self.calls.append((url, headers))

                class _Resp:
                    status_code = self._status

                return _Resp()

        healthy = _FakeAsyncClient(200)
        original = httpx.AsyncClient
        httpx.AsyncClient = lambda: healthy
        try:
            self.assertTrue(run(connector.connect()))
        finally:
            httpx.AsyncClient = original
        url, headers = healthy.calls[0]
        self.assertIn("/pn", url)
        self.assertEqual(headers["Authorization"], "Bearer tok")

        unhealthy = _FakeAsyncClient(401)
        httpx.AsyncClient = lambda: unhealthy
        try:
            self.assertFalse(run(connector.connect()))
        finally:
            httpx.AsyncClient = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
