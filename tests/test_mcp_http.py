"""Streamable-HTTP MCP transport tests (POST /mcp, /.well-known/mcp)."""

import asyncio
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient


class HttpMcpTestCase(unittest.TestCase):
    def setUp(self):
        import backend.database as database
        import backend.main as main_mod

        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "http.db"
        import os

        self._gate = os.environ.pop("AUTOPILOT_MCP_ALLOW_MUTATIONS", None)
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        if self._gate is not None:
            import os

            os.environ["AUTOPILOT_MCP_ALLOW_MUTATIONS"] = self._gate
        self._tmp.cleanup()

    def post(self, payload) -> object:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return self.client.post("/mcp", content=body,
                                headers={"Content-Type": "application/json"})

    def test_initialize_over_http(self):
        response = self.post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["serverInfo"]["name"], "autopilot-fde")
        self.assertEqual(result["protocolVersion"], "2024-11-05")

    def test_tools_call_roundtrip_over_http(self):
        self.post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = self.post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = [t["name"] for t in listed.json()["result"]["tools"]]
        self.assertIn("dashboard_summary", tools)

        called = self.post({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "dashboard_summary", "arguments": {}},
        })
        summary = json.loads(called.json()["result"]["content"][0]["text"])
        self.assertGreaterEqual(summary["processes_discovered"], 0)

    def test_malformed_body_returns_parse_error(self):
        response = self.post(b"{broken")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"]["code"], -32700)

    def test_non_dict_payload_returns_parse_error(self):
        response = self.post(b"[1,2,3]")
        self.assertEqual(response.json()["error"]["code"], -32700)

    def test_empty_body_returns_parse_error(self):
        response = self.post(b"")
        self.assertEqual(response.json()["error"]["code"], -32700)

    def test_get_method_is_not_allowed(self):
        response = self.client.get("/mcp")
        self.assertEqual(response.status_code, 405)

    def test_notification_acknowledged_with_202(self):
        response = self.post({
            "jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(response.status_code, 202)

    def test_discovery_card_advertises_tools_and_gate_state(self):
        response = self.client.get("/.well-known/mcp")
        self.assertEqual(response.status_code, 200)
        card = response.json()
        self.assertEqual(card["serverInfo"]["name"], "autopilot-fde")
        self.assertFalse(card["mutationsEnabled"])
        names = {t["name"] for t in card["tools"]}
        self.assertIn("simulate_process", names)
        self.assertIn("deploy_agent", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
