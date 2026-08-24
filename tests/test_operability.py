"""v0.8.0 Operable Identity & Telemetry: OTLP env wiring + identity leases."""

import asyncio
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.security import (  # noqa: E402
    decode_agent_lease,
    issue_agent_lease,
    lease_seconds_remaining,
    verify_agent_token,
)


class TestEndpointResolution(unittest.TestCase):
    def tearDown(self):
        for key in ("AUTOPILOT_OTEL_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT",
                    "AUTOPILOT_SERVICE_NAME"):
            os.environ.pop(key, None)

    def test_precedence_and_trailing_slash(self):
        from backend.observability.export import resolve_endpoint

        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://std:4318"
        self.assertEqual(resolve_endpoint(), "http://std:4318")
        os.environ["AUTOPILOT_OTEL_OTLP_ENDPOINT"] = "http://auto:4318/"
        self.assertEqual(resolve_endpoint(), "http://auto:4318")
        os.environ.pop("AUTOPILOT_OTEL_OTLP_ENDPOINT")
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT")
        self.assertIsNone(resolve_endpoint())

    def test_trace_url_appends_path_once(self):
        from backend.observability.export import trace_url

        self.assertEqual(trace_url("http://c:4318"), "http://c:4318/v1/traces")
        self.assertEqual(trace_url("http://c:4318/v1/traces"),
                         "http://c:4318/v1/traces")


class FakeProvider:
    def __init__(self, resource=None):
        self.resource = resource
        self.processors = []

    def add_span_processor(self, processor):
        self.processors.append(processor)


class FakeTraceModule:
    provider = None

    @staticmethod
    def get_tracer_provider():
        return FakeTraceModule.provider or SimpleNamespace(resource=None)

    @staticmethod
    def set_tracer_provider(provider):
        FakeTraceModule.provider = provider


class SimpleDeps:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def fake_deps(record):
    def exporter_cls(endpoint=None):
        record["exporter_endpoint"] = endpoint
        return object()

    def processor_cls(exporter):
        record["processor_for"] = exporter
        return ("proc", exporter)

    def provider_cls(resource=None):
        record["resource"] = resource
        return FakeProvider(resource=resource)

    def resource_create(attrs):
        record["service"] = attrs.get("service.name")
        return {"svc": attrs.get("service.name")}

    return SimpleDeps(
        TracerProvider=provider_cls,
        BatchSpanProcessor=processor_cls,
        OTLPSpanExporter=exporter_cls,
        Resource=SimpleNamespace(create=staticmethod(resource_create)),
        trace=FakeTraceModule,
    )


class TestConfigureFromEnv(unittest.TestCase):
    def setUp(self):
        FakeTraceModule.provider = None
        self._saved = {k: os.environ.get(k) for k in (
            "AUTOPILOT_OTEL_OTLP_ENDPOINT", "AUTOPILOT_SERVICE_NAME")}
        os.environ["AUTOPILOT_OTEL_OTLP_ENDPOINT"] = "http://collector:4318"

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_disabled_without_endpoint(self):
        from backend.observability import export as otel_export

        os.environ.pop("AUTOPILOT_OTEL_OTLP_ENDPOINT", None)
        status = otel_export.configure_from_env(deps=fake_deps({}))
        self.assertFalse(status["enabled"])
        self.assertIn("endpoint", status["reason"])

    def test_disabled_without_extra(self):
        from backend.observability import export as otel_export

        with mock.patch.object(otel_export, "_load_deps", return_value=None):
            status = otel_export.configure_from_env()
        self.assertFalse(status["enabled"])
        self.assertIn("extra", status["reason"])

    def test_full_wiring_sets_provider_and_processor(self):
        from backend.observability import export as otel_export

        record: dict = {}
        deps = fake_deps(record)
        with mock.patch.object(otel_export, "_load_deps", return_value=deps):
            status = otel_export.configure_from_env()
        self.assertTrue(status["enabled"], status)
        self.assertEqual(status["endpoint"],
                         "http://collector:4318/v1/traces")
        self.assertEqual(status["service"], "autopilot-fde")
        self.assertEqual(record["exporter_endpoint"],
                         "http://collector:4318/v1/traces")
        self.assertIsNotNone(FakeTraceModule.provider)
        del record

    def test_existing_provider_gets_processor_not_replaced(self):
        from backend.observability import export as otel_export

        existing = FakeProvider(resource={"svc": "x"})
        FakeTraceModule.provider = existing
        record: dict = {}
        with mock.patch.object(otel_export, "_load_deps",
                               return_value=fake_deps(record)):
            status = otel_export.configure_from_env()
        self.assertTrue(status["enabled"])
        self.assertIs(FakeTraceModule.provider, existing)
        self.assertGreaterEqual(len(existing.processors), 1)

    def test_wiring_error_degrades_to_disabled(self):
        from backend.observability import export as otel_export

        class Boom:
            def __getattr__(self, name):
                raise RuntimeError("boom")

        with mock.patch.object(otel_export, "_load_deps", return_value=Boom()):
            status = otel_export.configure_from_env()
        self.assertFalse(status["enabled"])
        self.assertIn("wiring error", status["reason"])

    def test_service_name_override(self):
        from backend.observability import export as otel_export

        os.environ["AUTOPILOT_SERVICE_NAME"] = "autopilot-staging"
        record: dict = {}
        with mock.patch.object(otel_export, "_load_deps",
                               return_value=fake_deps(record)):
            status = otel_export.configure_from_env()
        self.assertEqual(status["service"], "autopilot-staging")


SECRET = "lease-secret"


class TestAgentLeases(unittest.TestCase):
    def test_issue_decode_roundtrip_with_expiry(self):
        token = issue_agent_lease("agent-l", ttl_seconds=600, secret=SECRET,
                                  now=1_000_000)
        payload = decode_agent_lease(token, secret=SECRET)
        self.assertEqual(payload["aid"], "agent-l")
        self.assertEqual(payload["iat"], 1_000_000)
        self.assertEqual(payload["exp"], 1_000_600)
        self.assertEqual(lease_seconds_remaining(payload, now=1_000_100), 500)

    def test_expired_lease_fails_verification(self):
        token = issue_agent_lease("agent-l", ttl_seconds=10, secret=SECRET,
                                  now=1_000_000)
        self.assertFalse(verify_agent_token("agent-l", token,
                                            secret=SECRET, now=1_000_011))
        self.assertTrue(verify_agent_token("agent-l", token,
                                           secret=SECRET, now=1_000_005))

    def test_wrong_agent_or_secret_rejected(self):
        token = issue_agent_lease("agent-a", secret=SECRET)
        self.assertFalse(verify_agent_token("agent-b", token, secret=SECRET))
        self.assertFalse(verify_agent_token("agent-a", token, secret="other"))

    def test_tampered_payload_breaks_signature(self):
        token = issue_agent_lease("agent-t", secret=SECRET)
        head, body, sig = token.split(".")
        forged_body = body[:-2] + ("AA" if not body.endswith("AA") else "BB")
        forged = f"v1.{forged_body}.{sig}"
        self.assertIsNone(decode_agent_lease(forged, secret=SECRET))
        self.assertFalse(verify_agent_token("agent-t", forged, secret=SECRET))

    def test_malformed_shapes_return_none_false(self):
        self.assertIsNone(decode_agent_lease("v1.onlytwo", secret=SECRET))
        self.assertIsNone(decode_agent_lease("v1.a.b", secret="no-such"))
        self.assertFalse(verify_agent_token("a", "v1.!!!.zz", secret=SECRET))

    def test_static_tokens_still_verify_alongside_leases(self):
        static = __import__("backend.security", fromlist=["issue_agent_token"]) \
            .issue_agent_token("agent-s", secret=SECRET)
        self.assertTrue(verify_agent_token("agent-s", static, secret=SECRET))

    def test_no_secret_disables_leases(self):
        old = {k: os.environ.get(k) for k in ("AUTOPILOT_AGENT_SECRET",
                                              "AUTOPILOT_API_KEY")}
        try:
            for k in old:
                os.environ.pop(k, None)
            self.assertIsNone(issue_agent_lease("agent-x"))
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestLoadDepsStubbed(unittest.TestCase):
    def test_load_deps_builds_surface_from_installed_extra(self):
        import importlib
        import types

        from backend.observability import export as otel_export

        names_root = "opentelemetry"
        saved = dict(sys.modules)

        def mk(name):
            mod = types.ModuleType(name)
            mod.__path__ = []
            sys.modules[name] = mod
            return mod

        otel = mk(names_root)
        for name in ("opentelemetry.exporter",
                     "opentelemetry.exporter.otlp",
                     "opentelemetry.exporter.otlp.proto",
                     "opentelemetry.exporter.otlp.proto.http"):
            mk(name)
        te = mk("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        te.OTLPSpanExporter = lambda endpoint=None: ("exp", endpoint)
        res = mk("opentelemetry.sdk.resources")
        res.Resource = SimpleNamespace(create=staticmethod(lambda a: a))
        tr = mk("opentelemetry.sdk.trace")
        tr.TracerProvider = lambda resource=None: ("prov", resource)
        ex = mk("opentelemetry.sdk.trace.export")
        ex.BatchSpanProcessor = lambda e: ("bsp", e)
        otel.trace = types.ModuleType("opentelemetry.trace")

        old_flag = otel_export._TRACING_AVAILABLE
        otel_export._TRACING_AVAILABLE = True
        try:
            deps = otel_export._load_deps()
            self.assertIsNotNone(deps)
            self.assertEqual(deps.Resource.create({"service.name": "s"}),
                             {"service.name": "s"})
        finally:
            otel_export._TRACING_AVAILABLE = old_flag
            sys.modules.clear()
            sys.modules.update(saved)
            importlib.reload(__import__(
                "backend.observability.tracing", fromlist=["reload"]))


class TestLeaseDecodeEdgeBranches(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("AUTOPILOT_AGENT_SECRET",
                                                      "AUTOPILOT_API_KEY")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_decode_without_any_secret_is_none(self):
        self.assertIsNone(decode_agent_lease("v1.a.b"))

    def test_non_json_payload_rejected(self):
        from backend.security import _b64url_encode

        body = _b64url_encode(b"not-json")
        import hashlib
        import hmac as hmac_mod

        sig = hmac_mod.new(SECRET.encode(), f"lease:{body}".encode(),
                           hashlib.sha256).hexdigest()
        token = f"v1.{body}.{sig}"
        self.assertIsNone(decode_agent_lease(token, secret=SECRET))

    def test_payload_missing_fields_rejected(self):
        from backend.security import _b64url_encode

        body = _b64url_encode(b"{}")
        import hashlib
        import hmac as hmac_mod

        sig = hmac_mod.new(SECRET.encode(), f"lease:{body}".encode(),
                           hashlib.sha256).hexdigest()
        self.assertIsNone(decode_agent_lease(f"v1.{body}.{sig}", secret=SECRET))

    def test_non_numeric_exp_has_no_remaining(self):
        self.assertIsNone(lease_seconds_remaining({"exp": "soon"}))


class TestLeaseEndpoint(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "lease.db"
        self._saved = {k: os.environ.get(k) for k in ("AUTOPILOT_API_KEY",
                                                      "AUTOPILOT_AGENT_SECRET")}
        os.environ["AUTOPILOT_API_KEY"] = "k1"
        os.environ["AUTOPILOT_AGENT_SECRET"] = "s1"
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
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def _agent_id(self):
        process = self.client.get("/api/processes/").json()[0]
        score = self.client.get(f"/api/scores/{process['id']}").json()
        response = self.client.post("/api/agents/deploy",
                                    headers={"X-API-Key": "k1"},
                                    json={
            "process_id": process["id"], "name": "Lease Copilot",
            "config": {"mode": "draft", "approval_required": True,
                       "enabled_steps": score["eligible_steps"][:1]}})
        return response.json()["id"]

    def test_issue_requires_key_then_returns_verifiable_lease(self):
        agent_id = self._agent_id()
        unauth = self.client.post(f"/api/agents/{agent_id}/lease")
        self.assertEqual(unauth.status_code, 401)
        issued = self.client.post(f"/api/agents/{agent_id}/lease",
                                  headers={"X-API-Key": "k1"})
        self.assertEqual(issued.status_code, 200, issued.text)
        body = issued.json()
        self.assertEqual(body["expires_in"], 900)
        self.assertTrue(verify_agent_token(agent_id, body["lease"]))
        self.assertFalse(verify_agent_token("other", body["lease"]))

    def test_missing_agent_404_and_disabled_503(self):
        agent_id = self._agent_id()
        missing = self.client.post("/api/agents/agent-missing/lease",
                                   headers={"X-API-Key": "k1"})
        self.assertEqual(missing.status_code, 404)
        os.environ.pop("AUTOPILOT_AGENT_SECRET", None)
        os.environ.pop("AUTOPILOT_API_KEY", None)
        os.environ.pop("AUTOPILOT_AGENT_SECRET", None)
        os.environ.pop("AUTOPILOT_API_KEY", None)
        disabled = self.client.post(f"/api/agents/{agent_id}/lease")
        self.assertEqual(disabled.status_code, 503)


class TestLoadDepsUnavailable(unittest.TestCase):
    def test_load_deps_returns_none_when_extra_absent(self):
        from backend.observability import export as otel_export

        with mock.patch.object(otel_export, "_TRACING_AVAILABLE", False):
            self.assertIsNone(otel_export._load_deps())
