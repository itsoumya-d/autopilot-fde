"""MCP stdio server tests: handshake, tool listing, gating, transitions.

The protocol layer is exercised through ``handle_message_sync`` against an
isolated temp-store workspace seeded by the demo fixture; the wire format
(line-delimited JSON-RPC) is exercised end-to-end in TestSubprocessWire.
"""

import asyncio
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend import database, mcp_server, services  # noqa: E402


class McpWorkspaceTestCase(unittest.TestCase):
    """Isolated DB with demo data + one discovery pass."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = pathlib.Path(self._tmp.name) / "mcp.db"
        self._old_gate = os.environ.pop("AUTOPILOT_MCP_ALLOW_MUTATIONS", None)
        asyncio.run(self._seed())

    async def _seed(self):
        await database.init_db()
        from backend.demo_data import demo_channel, demo_messages

        if not await database.get_channels():
            await database.upsert_channel(demo_channel())
            await database.create_messages(demo_messages())
        if not await database.get_processes():
            await services.run_discovery()

    def tearDown(self):
        asyncio.run(database.close_db())
        if self._old_gate is not None:
            os.environ["AUTOPILOT_MCP_ALLOW_MUTATIONS"] = self._old_gate
        else:
            os.environ.pop("AUTOPILOT_MCP_ALLOW_MUTATIONS", None)
        self._tmp.cleanup()

    def rpc(self, method, params=None, msg_id=1):
        message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            message["params"] = params
        return mcp_server.handle_message_sync(message)

    def first_process_id(self):
        response = self.rpc("tools/call", {"name": "list_processes", "arguments": {}})
        payload = json.loads(response["result"]["content"][0]["text"])
        return payload["processes"][0]["id"]


class TestHandshake(McpWorkspaceTestCase):
    def test_initialize_negotiates_protocol(self):
        result = self.rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "autopilot-fde")
        self.assertIn("tools", result["capabilities"])

    def test_unknown_version_falls_back_to_supported(self):
        result = self.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(result["protocolVersion"], mcp_server.PROTOCOL_VERSION)

    def test_ping_returns_empty_result(self):
        self.assertEqual(self.rpc("ping")["result"], {})

    def test_unknown_method_is_minus_32601(self):
        error = self.rpc("resources/list")["error"]
        self.assertEqual(error["code"], -32601)

    def test_notifications_produce_no_response(self):
        self.assertIsNone(mcp_server.handle_message_sync({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }))

    def test_internal_error_envelope_for_broken_handler(self):
        async def broken(_args):
            raise RuntimeError("kaboom")

        original = dict(mcp_server.HANDLERS)
        mcp_server.HANDLERS["dashboard_summary"] = broken
        try:
            response = self.rpc("tools/call",
                                {"name": "dashboard_summary", "arguments": {}})
        finally:
            mcp_server.HANDLERS.clear()
            mcp_server.HANDLERS.update(original)
        self.assertEqual(response["error"]["code"], mcp_server.INTERNAL_ERROR)


class TestServeLoop(McpWorkspaceTestCase):
    """Drive serve() in-process: mocked stdin lines -> stdout JSON-RPC."""

    def _run_serve(self, lines):
        from io import StringIO
        from unittest import mock as mock_mod

        queue = list(lines)
        fake_stdin = type("FakeStdin", (), {
            "readline": staticmethod(lambda: queue.pop(0) if queue else ""),
        })()
        buffer = StringIO()

        import backend.mcp_server as server_mod

        with mock_mod.patch.object(server_mod.sys, "stdin", fake_stdin), \
             mock_mod.patch.object(server_mod.sys, "stdout", buffer):
            asyncio.run(server_mod.serve())
        return [json.loads(line) for line in buffer.getvalue().splitlines() if line]

    def test_loop_handles_valid_invalid_and_notification_traffic(self):
        responses = self._run_serve([
            "{not json\n",                                   # parse error (id null)
            "[1, 2]\n",                                      # non-dict parse error
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}) + "\n",
            json.dumps({"jsonrpc": "2.0", "method":
                        "notifications/initialized"}) + "\n",  # no reply
            "\n",                                            # blank line skipped
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n",
        ])
        self.assertEqual(len(responses), 4)  # notification + blank produce none
        parse_errors = [r for r in responses if r.get("error")]
        self.assertEqual(len(parse_errors), 2)
        self.assertTrue(all(e["error"]["code"] == mcp_server.PARSE_ERROR
                            for e in parse_errors))
        ping = next(r for r in responses if r.get("id") == 2)
        self.assertEqual(ping["result"], {})
        init = next(r for r in responses if r.get("id") == 1)
        self.assertIn("serverInfo", init["result"])

    def test_main_invokes_asyncio_run_with_serve(self):
        from unittest import mock as mock_mod

        with mock_mod.patch("backend.mcp_server.asyncio.run") as run_mock:
            mcp_server.main()
        run_mock.assert_called_once()

    def test_configure_db_path_relocates_workspace(self):
        override = pathlib.Path(self._tmp.name) / "relocated.db"
        original = os.environ.pop("AUTOPILOT_DB_PATH", None)
        os.environ["AUTOPILOT_DB_PATH"] = str(override)
        try:
            mcp_server._configure_db_path()
            import backend.database as database

            self.assertEqual(database.DB_PATH, override)
        finally:
            if original is None:
                os.environ.pop("AUTOPILOT_DB_PATH", None)
            else:
                os.environ["AUTOPILOT_DB_PATH"] = original


class TestToolSurface(McpWorkspaceTestCase):
    def test_tools_list_advertises_read_and_mutating_tools(self):
        tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}
        for expected in ("dashboard_summary", "list_processes", "get_process",
                         "get_scores", "recommendations", "simulate_process",
                         "list_channels", "list_agents"):
            self.assertIn(expected, tools)
        for expected in ("run_discovery", "deploy_agent", "approve_agent",
                         "pause_agent", "resume_agent", "stop_agent"):
            self.assertIn(expected, tools)
        self.assertTrue(all("inputSchema" in t for t in tools.values()))

    def test_disabled_mutations_are_flagged_in_descriptions(self):
        tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertNotIn("DISABLED", tools["dashboard_summary"]["description"])
        self.assertIn("DISABLED", tools["deploy_agent"]["description"])
        self.assertIn("MUTATING", tools["approve_agent"]["description"])

    def test_dashboard_summary_roundtrip(self):
        response = self.rpc("tools/call", {"name": "dashboard_summary", "arguments": {}})
        self.assertNotIn("isError", response["result"])
        summary = json.loads(response["result"]["content"][0]["text"])
        self.assertGreater(summary["processes_discovered"], 0)

    def test_get_process_requires_argument(self):
        response = self.rpc("tools/call", {"name": "get_process", "arguments": {}})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("process_id", response["result"]["content"][0]["text"])

    def test_get_process_returns_full_detail(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {"name": "get_process", "arguments": {"process_id": pid}})
        detail = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(detail["id"], pid)
        self.assertIsInstance(detail["activities"], list)

    def test_unknown_tool_is_error_result_not_crash(self):
        response = self.rpc("tools/call", {"name": "does_not_exist", "arguments": {}})
        self.assertTrue(response["result"]["isError"])

    def test_simulate_rejects_out_of_range_runs(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {
            "name": "simulate_process",
            "arguments": {"process_id": pid, "runs": 10},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("100", response["result"]["content"][0]["text"])

    def test_recommendations_shape(self):
        response = self.rpc("tools/call", {"name": "recommendations", "arguments": {}})
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertGreater(payload["count"], 0)
        self.assertIn("wave", payload["recommendations"][0])

    def test_scores_channels_and_agents_tools_roundtrip(self):
        for tool in ("get_scores", "list_channels", "list_agents"):
            response = self.rpc("tools/call", {"name": tool, "arguments": {}})
            self.assertNotIn("isError", response["result"], tool)
            payload = json.loads(response["result"]["content"][0]["text"])
            self.assertGreaterEqual(payload["count"], 0)

    def test_simulate_rejects_non_numeric_runs(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {
            "name": "simulate_process",
            "arguments": {"process_id": pid, "runs": "many"},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("Invalid numeric", response["result"]["content"][0]["text"])

    def test_simulate_rejects_out_of_range_threshold(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {
            "name": "simulate_process",
            "arguments": {"process_id": pid, "confidence_threshold": 0.1},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("confidence_threshold", response["result"]["content"][0]["text"])

    def test_call_tool_rejects_non_dict_arguments(self):
        response = self.rpc("tools/call", {"name": "dashboard_summary",
                                           "arguments": "not-a-dict"})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("object", response["result"]["content"][0]["text"])

    def test_simulate_happy_path_returns_forecast(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {
            "name": "simulate_process",
            "arguments": {"process_id": pid, "runs": 100},
        })
        self.assertNotIn("isError", response["result"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertIn("straight_through_rate", payload)


class TestMutationGate(McpWorkspaceTestCase):
    def test_mutations_refused_without_consent_env(self):
        response = self.rpc("tools/call", {"name": "run_discovery", "arguments": {}})
        self.assertTrue(response["result"]["isError"])
        text = response["result"]["content"][0]["text"]
        self.assertIn(mcp_server.MUTATIONS_ENV, text)

    def test_deploy_refused_without_consent_even_with_valid_args(self):
        pid = self.first_process_id()
        response = self.rpc("tools/call", {
            "name": "deploy_agent",
            "arguments": {"process_id": pid, "name": "MCP Deploy Probe"},
        })
        self.assertTrue(response["result"]["isError"])

    def test_autonomous_mode_refused_even_with_consent(self):
        os.environ["AUTOPILOT_MCP_ALLOW_MUTATIONS"] = "1"
        try:
            pid = self.first_process_id()
            response = self.rpc("tools/call", {
                "name": "deploy_agent",
                "arguments": {"process_id": pid, "name": "Autonomous Probe",
                              "mode": "autonomous"},
            })
            self.assertTrue(response["result"]["isError"])
            self.assertIn("AUTONOMOUS", response["result"]["content"][0]["text"])
        finally:
            os.environ.pop("AUTOPILOT_MCP_ALLOW_MUTATIONS", None)


class TestMutationsWithConsent(McpWorkspaceTestCase):
    def setUp(self):
        super().setUp()
        os.environ["AUTOPILOT_MCP_ALLOW_MUTATIONS"] = "1"

    def test_tools_list_marks_mutations_enabled(self):
        tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertIn("ENABLED", tools["deploy_agent"]["description"])

    def test_transition_without_agent_id_is_error(self):
        for tool in ("approve_agent", "pause_agent", "resume_agent", "stop_agent"):
            response = self.rpc("tools/call", {"name": tool, "arguments": {}})
            self.assertTrue(response["result"]["isError"], tool)
            self.assertIn("agent_id is required",
                          response["result"]["content"][0]["text"])

    def test_deploy_argument_validation_matrix(self):
        pid = self.first_process_id()
        cases = [
            ({"process_id": "", "name": "Valid Name Here"}, "process_id is required"),
            ({"process_id": pid, "name": "ab"}, "name must be 3-80"),
            ({"process_id": "proc-missing", "name": "Valid Name Here"}, "not found"),
            ({"process_id": pid, "name": "Valid Name Here", "mode": "chaotic"},
             "Unknown mode"),
        ]
        for arguments, expected in cases:
            response = self.rpc("tools/call", {"name": "deploy_agent",
                                               "arguments": arguments})
            self.assertTrue(response["result"]["isError"], arguments)
            self.assertIn(expected, response["result"]["content"][0]["text"])

    def test_deploy_rejects_ineligible_steps(self):
        pid = self.first_process_id()
        score = asyncio.run(database.get_score(pid))
        bogus = f"Not a real step ({score.eligible_steps!r} are eligible)"
        response = self.rpc("tools/call", {
            "name": "deploy_agent",
            "arguments": {"process_id": pid, "name": "Valid Name Here",
                          "enabled_steps": ["Definitely Not A Step"]},
        })
        del bogus
        self.assertTrue(response["result"]["isError"])
        self.assertIn("not eligible", response["result"]["content"][0]["text"])

    def test_deploy_compile_failure_returns_error(self):
        from types import SimpleNamespace
        from unittest import mock as mock_mod

        from backend.deployment.agent_factory import AgentFactory

        pid = self.first_process_id()
        broken = SimpleNamespace(
            python_code="def oops(:\n    pass",
            process_id=pid, agent_name="Broken", tools=[],
            entrypoint="", langgraph_spec={},
        )
        with mock_mod.patch.object(AgentFactory, "generate_langgraph_code",
                                   return_value=broken):
            response = self.rpc("tools/call", {
                "name": "deploy_agent",
                "arguments": {"process_id": pid, "name": "Broken Build Copilot"},
            })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("failed validation", response["result"]["content"][0]["text"])

    def test_full_lifecycle_via_mcp_tools(self):
        pid = self.first_process_id()
        score = asyncio.run(database.get_score(pid))
        deployed = json.loads(self.rpc("tools/call", {
            "name": "deploy_agent",
            "arguments": {"process_id": pid, "name": "MCP Lifecycle Copilot",
                          "enabled_steps": score.eligible_steps[:1]},
        })["result"]["content"][0]["text"])
        agent_id = deployed["agent_id"]
        self.assertEqual(deployed["status"], "pending_approval")
        self.assertEqual(deployed["enabled_steps"], score.eligible_steps[:1])

        approved = json.loads(self.rpc("tools/call", {
            "name": "approve_agent", "arguments": {"agent_id": agent_id},
        })["result"]["content"][0]["text"])
        self.assertEqual(approved["status"], "running")

        paused = json.loads(self.rpc("tools/call", {
            "name": "pause_agent", "arguments": {"agent_id": agent_id},
        })["result"]["content"][0]["text"])
        self.assertEqual(paused["status"], "paused")

        stopped = json.loads(self.rpc("tools/call", {
            "name": "stop_agent", "arguments": {"agent_id": agent_id},
        })["result"]["content"][0]["text"])
        self.assertEqual(stopped["status"], "stopped")

        illegal = self.rpc("tools/call", {
            "name": "resume_agent", "arguments": {"agent_id": agent_id},
        })
        self.assertTrue(illegal["result"]["isError"])
        self.assertIn("Illegal transition", illegal["result"]["content"][0]["text"])

    def test_audit_trail_records_mcp_actor(self):
        pid = self.first_process_id()
        deployed = json.loads(self.rpc("tools/call", {
            "name": "deploy_agent",
            "arguments": {"process_id": pid, "name": "MCP Audit Copilot"},
        })["result"]["content"][0]["text"])
        self.rpc("tools/call", {"name": "approve_agent",
                                "arguments": {"agent_id": deployed["agent_id"]}})
        agent = asyncio.run(database.get_agent(deployed["agent_id"]))
        actors = [entry["actor"] for entry in agent.metrics["audit"]]
        self.assertEqual(actors, ["mcp-agent", "mcp-agent"])

    def test_transition_on_missing_agent_is_error(self):
        response = self.rpc("tools/call", {"name": "approve_agent",
                                           "arguments": {"agent_id": "agent-missing"}})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("Agent not found", response["result"]["content"][0]["text"])

    def test_corrupt_audit_trail_is_repaired_not_fatal(self):
        pid = self.first_process_id()
        deployed = json.loads(self.rpc("tools/call", {
            "name": "deploy_agent",
            "arguments": {"process_id": pid, "name": "Corrupt Trail Copilot"},
        })["result"]["content"][0]["text"])
        agent = asyncio.run(database.get_agent(deployed["agent_id"]))
        agent.metrics["audit"] = "corrupted-by-bug"
        asyncio.run(database.save_agent(agent))

        approved = self.rpc("tools/call", {
            "name": "approve_agent", "arguments": {"agent_id": agent.id}})
        self.assertNotIn("isError", approved["result"])
        repaired = asyncio.run(database.get_agent(agent.id))
        self.assertIsInstance(repaired.metrics["audit"], list)
        # The corrupt value was discarded wholesale; approve lands in a clean trail.
        actions = [entry["action"] for entry in repaired.metrics["audit"]]
        self.assertEqual(actions, ["approve"])

    def test_run_discovery_tool_executes_with_consent(self):
        response = self.rpc("tools/call", {"name": "run_discovery",
                                           "arguments": {}})
        self.assertNotIn("isError", response["result"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["message"], "Discovery complete")
        self.assertGreaterEqual(payload["processes"], 0)


class TestSubprocessWire(McpWorkspaceTestCase):
    """End-to-end: spawn `python -m backend.mcp_server`, speak line JSON."""

    def test_wire_protocol_handshake_and_tool_call(self):
        env = dict(os.environ)
        env.pop("AUTOPILOT_MCP_ALLOW_MUTATIONS", None)
        env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[1])
        env["AUTOPILOT_DB_PATH"] = str(database.DB_PATH)
        proc = subprocess.Popen(
            [sys.executable, "-m", "backend.mcp_server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env,
            cwd=str(pathlib.Path(__file__).resolve().parents[1]),
        )
        try:
            init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()
            init_resp = json.loads(proc.stdout.readline())
            self.assertEqual(init_resp["result"]["serverInfo"]["name"], "autopilot-fde")

            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized"
            }) + "\n")
            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0", "id": 2,
                "method": "tools/call",
                "params": {"name": "dashboard_summary", "arguments": {}},
            }) + "\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline()
                if not line:
                    self.fail("server closed before responding")
                parsed = json.loads(line)
                if parsed.get("id") == 2:
                    break
            summary = json.loads(parsed["result"]["content"][0]["text"])
            self.assertGreater(summary["processes_discovered"], 0)
        finally:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
