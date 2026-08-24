"""LangGraph-native codegen (v2) tests: interrupt gates, checkpointer, topology.

Pins what makes emitted agents first-class LangGraph citizens:
- HITL steps become dedicated gate_* nodes calling native interrupt()
- the graph compiles with a checkpointer (SqliteSaver when configured)
- mined Process.edges drive topology when complete; linear fallback otherwise
- a langgraph.json ships alongside graph.py for Studio / `langgraph dev`
"""

import ast
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.deployment.agent_factory import AgentFactory  # noqa: E402
from backend.models.schema import (  # noqa: E402
    Activity,
    DeploymentConfig,
    DeploymentMode,
    Process,
    ProcessEdge,
)


def _process(edges=None, steps=("Lead captured", "Demo scheduled",
                                "Quote schedule drafted", "Contract sent for execution")):
    return Process(
        id="proc-codegen", name="Deal Desk", category="sales",
        activities=[
            Activity(id=f"a-{i}", name=name, category="sales",
                     timestamp=__import__("datetime").datetime.now(
                         __import__("datetime").UTC))
            for i, name in enumerate(steps)
        ],
        edges=edges or [],
    )

_ALL_ENABLED = DeploymentConfig(
    mode=DeploymentMode.ASSISTED, approval_required=True,
    enabled_steps=["Lead captured", "Demo scheduled", "Quote schedule drafted"])

_CONFIG = DeploymentConfig(mode=DeploymentMode.ASSISTED, approval_required=True,
                           enabled_steps=["Lead captured", "Demo scheduled"])


class TestNativeInterruptGates(unittest.TestCase):
    def setUp(self):
        self.code = AgentFactory().generate_langgraph_code(
            _process(), _ALL_ENABLED, "Codegen Copilot").python_code

    def test_hitl_uses_native_interrupt_in_dedicated_gate_nodes(self):
        self.assertIn("from langgraph.types import interrupt", self.code)
        self.assertNotIn("HumanApprovalRequired", self.code)
        self.assertIn("def gate_contract_sent_for_execution(", self.code)
        gate_body = self.code.split("def gate_contract_sent_for_execution(")[1]
        # Approval-only node: interrupt() before any history mutation, so the
        # documented resume-restarts-node semantics cannot double-fire effects.
        self.assertLess(gate_body.index("interrupt({"),
                        gate_body.index("history.append"))

    def test_automated_nodes_dispatch_risk_tiered_adapter(self):
        self.assertIn('execute_agent_step(step_name="Demo scheduled"', self.code)

    def test_graph_compiles_with_checkpointer(self):
        self.assertIn("workflow.compile(checkpointer=_default_checkpointer())", self.code)
        self.assertIn("AUTOPILOT_CHECKPOINT_DB", self.code)

    def test_emitted_source_is_valid_python(self):
        ast.parse(self.code)
        compile(self.code, "<generated>", "exec")


class TestTopology(unittest.TestCase):
    def _factory(self):
        return AgentFactory()

    def test_complete_mined_edges_drive_topology(self):
        process = _process(
            steps=("Lead captured", "Demo scheduled", "Payment confirmed"),
            edges=[
                ProcessEdge(source="Lead captured", target="Demo scheduled",
                            probability=1.0),
                ProcessEdge(source="Demo scheduled", target="Payment confirmed",
                            probability=0.8),
            ],
        )
        code = self._factory().generate_langgraph_code(process, _CONFIG, "Topo Copilot")
        self.assertEqual(code.langgraph_spec["topology"], "mined_edges")
        self.assertEqual(code.langgraph_spec["entrypoint_node"], "node_lead_captured")
        self.assertIn('workflow.add_edge("node_demo_scheduled", '
                      '"gate_payment_confirmed")', code.python_code)
        self.assertIn('workflow.add_edge("gate_payment_confirmed", END)',
                      code.python_code)

    def test_incomplete_mined_edges_fall_back_linear(self):
        # Missing the terminal step -> not every step is touched by edges.
        process = _process(edges=[
            ProcessEdge(source="Lead captured", target="Demo scheduled",
                        probability=1.0),
        ])
        code = self._factory().generate_langgraph_code(process, _CONFIG, "Fallback Copilot")
        self.assertEqual(code.langgraph_spec["topology"], "linear_fallback")
        self.assertIn("# Topology: linear_fallback", code.python_code)

    def test_unknown_edge_endpoints_reject_topology(self):
        process = _process(edges=[
            ProcessEdge(source="Ghost step", target="Demo scheduled", probability=1.0),
        ])
        code = self._factory().generate_langgraph_code(process, _CONFIG, "Ghost Copilot")
        self.assertEqual(code.langgraph_spec["topology"], "linear_fallback")

    def test_entrypoint_qualifies_hitl_prefix_when_first_step_is_gated(self):
        config = DeploymentConfig(mode=DeploymentMode.DRAFT, approval_required=True,
                                  enabled_steps=["Lead captured"])
        process = _process(steps=("Payment confirmed",))
        code = self._factory().generate_langgraph_code(process, config, "Gate First")
        self.assertEqual(code.langgraph_spec["entrypoint_node"], "gate_payment_confirmed")


class TestLanggraphJsonEmission(unittest.TestCase):
    def test_langgraph_json_opens_agent_in_studio(self):
        generated = AgentFactory().generate_langgraph_code(
            _process(), _CONFIG, "Studio Copilot")
        config = generated.langgraph_json
        self.assertEqual(config["graphs"]["agent"], "./graph.py:app")
        self.assertIn("$schema", config)
        self.assertEqual(config["metadata"]["agent_name"], "Studio Copilot")

    def test_spec_reports_hitl_nodes(self):
        spec = AgentFactory().generate_langgraph_code(
            _process(), _ALL_ENABLED, "Spec Copilot").langgraph_spec
        self.assertIn("contract_sent_for_execution", spec["hitl_nodes"])
        # 3 automated nodes + the terminal approval gate.
        self.assertEqual(spec["nodes_count"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
