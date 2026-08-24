"""Autonomous Agent Branch & LangGraph Workflow Code Generator (v2).

Translates discovered business processes into *first-class* LangGraph state
machines:

- Human-in-the-loop gates use LangGraph's native ``interrupt()`` inside
  dedicated approval-only nodes, so resuming via ``Command(resume=...)``
  never re-fires side effects (the documented double-execution pitfall).
- The compiled graph is wired to a persistent checkpointer when
  ``AUTOPILOT_CHECKPOINT_DB`` is set (SqliteSaver), falling back to an
  in-memory saver for local runs -- paused approvals survive restarts.
- Graph topology honors mined ``Process.edges`` (probabilities preserved in
  the spec) instead of forcing a linear chain; unknown topologies fall back
  to a linear chain deterministically.
- A sibling ``langgraph.json`` is emitted so the agent opens directly in
  LangGraph Studio / `langgraph dev`.
"""

from uuid import uuid4

from backend.models.schema import (
    AgentBranch,
    AgentStatus,
    DeploymentConfig,
    GeneratedAgentCode,
    Process,
)


def _slugify(step_name: str) -> str:
    """A Python-identifier-safe node slug for a step name."""
    return "".join(c if c.isalnum() else "_" for c in step_name.lower()).strip("_")


class AgentFactory:
    """Creates deployed agent branches and synthesizes executable LangGraph workflow code."""

    def create_agent(
        self,
        process: Process,
        config: DeploymentConfig,
        name: str | None = None,
    ) -> AgentBranch:
        agent_name = name or f"{process.name} Copilot"
        generated_code = self.generate_langgraph_code(process, config, agent_name)

        return AgentBranch(
            id=f"agent-{uuid4().hex[:10]}",
            process_id=process.id,
            name=agent_name,
            # Every branch starts gated: an operator must approve it through the
            # API before it may execute anything.
            status=AgentStatus.PENDING_APPROVAL,
            config=config,
            metrics={
                "runs_executed": 0,
                "straight_through_completions": 0,
                "escalations_handled": 0,
                "total_tokens_consumed": 0,
                "average_execution_seconds": 0.0,
            },
            generated_code=generated_code,
        )

    def _is_hitl_step(self, step: str, index: int, total: int, config: DeploymentConfig) -> bool:
        node_slug = _slugify(step)
        return config.approval_required and (
            index == total - 1
            or "confirm" in node_slug
            or "pay" in node_slug
            or "approval" in node_slug
        )

    def generate_langgraph_code(
        self,
        process: Process,
        config: DeploymentConfig,
        agent_name: str,
    ) -> GeneratedAgentCode:
        """Generates runnable Python LangGraph workflow code with state schema and HITL checkpoints."""
        tools: list[str] = []
        registrations: list[str] = []

        step_names = [act.name for act in process.activities]
        hitl_slugs: set[str] = set()
        gate_definitions: list[str] = []
        node_defs: list[str] = []
        registrations: list[str] = []

        for index, step in enumerate(step_names):
            node_slug = _slugify(step)
            is_deployed = step in config.enabled_steps if config.enabled_steps else True
            is_hitl = self._is_hitl_step(step, index, len(step_names), config)

            if is_hitl:
                hitl_slugs.add(node_slug)
                # Dedicated approval-only node: its ONLY job is interrupt() +
                # recording the human decision, so LangGraph's resume-from-node-
                # start semantics can never re-fire business side effects.
                gate_definitions.append(f"""
def gate_{node_slug}(state: WorkflowState) -> dict:
    \"\"\"Human-in-the-Loop Gate: {step} (native LangGraph interrupt).\"\"\"
    context = state.get("payload", {{}})
    decision = interrupt({{
        "type": "human_approval",
        "step": "{step}",
        "context_preview": {{k: context[k] for k in list(context)[:10]}},
        "note": "Resume with Command(resume={{'approved': True|False, 'actor': '...'}})",
    }})
    history = state.get("step_history", [])
    history.append({{"step": "{step}", "status": "human_approved", "decision": decision}})
    return {{"step_history": history, "current_step": "{step}", "last_decision": decision}}
""".strip())
                registrations.append(f'workflow.add_node("gate_{node_slug}", gate_{node_slug})')
                tools.append(f"tool_{node_slug}")
                continue

            if not is_deployed:
                continue

            node_defs.append(f"""
def node_{node_slug}(state: WorkflowState) -> dict:
    \"\"\"Automated Step: {step}\"\"\"
    context = state.get("payload", {{}})
    result = execute_agent_step(step_name="{step}", context=context)
    history = state.get("step_history", [])
    history.append({{"step": "{step}", "status": "automated", "result": result}})
    return {{"step_history": history, "current_step": "{step}"}}
""".strip())
            registrations.append(f'workflow.add_node("node_{node_slug}", node_{node_slug})')
            tools.append(f"tool_{node_slug}")

        def _q(slug: str) -> str:
            """Full node id: HITL checkpoints live on gate_ prefixed nodes."""
            return f"gate_{slug}" if slug in hitl_slugs else f"node_{slug}"

        chain_order = [
            _slugify(s) for i, s in enumerate(step_names)
            if _slugify(s) in hitl_slugs
            or s in (config.enabled_steps or [s2.name for s2 in process.activities])
        ]
        edge_pairs = self._topology_pairs(process, chain_order)
        if edge_pairs is not None:
            first_id = _q(edge_pairs[0][0])
            assembly = self._assemble_from_pairs(edge_pairs, _q)
            topology = "mined_edges"
        else:
            first_slug = chain_order[0] if chain_order else "init"
            first_id = _q(first_slug)
            assembly = self._assemble_linear(chain_order, _q)
            topology = "linear_fallback"

        full_code = f'''"""Autonomously generated LangGraph agent workflow for {process.name}."""

import os
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
import operator

try:  # durable checkpoints when the sqlite extra is installed and configured
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:  # pragma: no cover - optional extra
    SqliteSaver = None
from langgraph.checkpoint.memory import InMemorySaver

from backend.deployment.tool_adapters import execute_agent_step as _dispatch_tool_step

class WorkflowState(TypedDict):
    case_id: str
    payload: Dict[str, Any]
    current_step: str
    step_history: Annotated[List[Dict[str, Any]], operator.add]
    is_escalated: bool
    last_decision: Dict[str, Any]

def execute_agent_step(step_name: str, context: dict) -> dict:
    # Dispatches through backend.deployment.tool_adapters: risk-tiered safe
    # adapters (read-only, draft writing, internal webhook). EXTERNAL_WRITE and
    # CRITICAL_TRANSACTION tiers raise StructuralGateError by construction.
    return _dispatch_tool_step(step_name=step_name, context=context)

def _default_checkpointer():
    """SqliteSaver when AUTOPILOT_CHECKPOINT_DB is set (and extra installed);
    in-memory otherwise. Paused approvals survive restarts only with SQLite."""
    db_path = os.getenv("AUTOPILOT_CHECKPOINT_DB")
    if db_path and SqliteSaver is not None:
        import sqlite3
        return SqliteSaver(sqlite3.connect(db_path, check_same_thread=False))
    return InMemorySaver()

# ── Node Definitions ────────────────────────────────────────────────────────
{chr(10).join(gate_definitions)}

{chr(10).join(node_defs)}

# ── State Graph Assembly ───────────────────────────────────────────────────
def build_agent_graph():
    workflow = StateGraph(WorkflowState)

    # Register nodes
{chr(10).join("    " + r for r in registrations)}

    # Topology: {topology}
{chr(10).join(assembly)}

    return workflow.compile(checkpointer=_default_checkpointer())

# Standalone execution entrypoint (LangGraph Studio / `langgraph dev` compatible)
app = build_agent_graph()
'''

        return GeneratedAgentCode(
            process_id=process.id,
            agent_name=agent_name,
            python_code=full_code,
            tools=tools,
            entrypoint="app = build_agent_graph()",
            langgraph_spec={
                "nodes_count": len(registrations),
                "edges_count": len(edge_pairs) if edge_pairs else max(len(chain_order) - 1, 0),
                "entrypoint_node": first_id,
                "terminal_node": "END",
                "hitl_nodes": sorted(hitl_slugs),
                "topology": topology,
            },
            langgraph_json=self.langgraph_config(agent_name),
        )

    def _topology_pairs(
        self, process: Process, chain_order: list[str],
    ) -> list[tuple[str, str]] | None:
        """Mined-edge topology mapped to slugs, or None when unusable.

        A mined topology is honored only when every edge references known
        steps and every step appears at least once -- otherwise work would be
        silently dropped, so we fall back to the deterministic linear chain.
        """
        valid = set(chain_order)
        pairs: list[tuple[str, str]] = []
        for edge in sorted(process.edges, key=lambda e: (-e.probability, e.source, e.target)):
            source, target = _slugify(edge.source), _slugify(edge.target)
            if source not in valid or target not in valid or source == target:
                return None
            if (source, target) not in pairs:
                pairs.append((source, target))
        if not pairs:
            return None
        touched = {n for pair in pairs for n in pair}
        if touched != valid:
            return None
        return pairs

    def _assemble_from_pairs(
        self, pairs: list[tuple[str, str]], qualify,
    ) -> list[str]:
        sources = {s for s, _ in pairs}
        targets = {t for _, t in pairs}
        lines = [f'workflow.set_entry_point("{qualify(pairs[0][0])}")']
        for source, target in pairs:
            lines.append(f'workflow.add_edge("{qualify(source)}", "{qualify(target)}")')
        for terminal in sorted(targets - sources):
            lines.append(f'workflow.add_edge("{qualify(terminal)}", END)')
        return ["    " + line for line in lines]

    def _assemble_linear(self, chain_order: list[str], qualify) -> list[str]:
        first = qualify(chain_order[0]) if chain_order else "node_init"
        lines = [f'workflow.set_entry_point("{first}")']
        for i in range(len(chain_order) - 1):
            lines.append(
                f'workflow.add_edge("{qualify(chain_order[i])}", '
                f'"{qualify(chain_order[i + 1])}")'
            )
        terminal = qualify(chain_order[-1]) if chain_order else first
        lines.append(f'workflow.add_edge("{terminal}", END)')
        return ["    " + line for line in lines]

    def langgraph_config(self, agent_name: str) -> dict:
        """A ready-to-save langgraph.json so Studio/dev-server open the agent."""
        return {
            "$schema": "https://langchain-ai.github.io/langgraph/langgraph.json",
            "dependencies": ["."],
            "graphs": {"agent": "./graph.py:app"},
            "env": ".env",
            "metadata": {"agent_name": agent_name},
        }
