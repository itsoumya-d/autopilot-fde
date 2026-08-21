"""Autonomous Agent Branch & LangGraph Workflow Code Generator.

Translates discovered business processes into verifiable, typed Python LangGraph state machines
with Human-in-the-Loop review gates and OpenAPI endpoints.
"""

from typing import Optional
from uuid import uuid4
from backend.models.schema import (
    AgentBranch,
    AgentStatus,
    DeploymentConfig,
    GeneratedAgentCode,
    Process,
    StepActionType,
)


def _indent_join(lines: list[str], indent: str = "    ") -> str:
    """Join generated statements so every line keeps the caller's indentation."""
    return ("\n" + indent).join(lines)


class AgentFactory:
    """Creates deployed agent branches and synthesizes executable LangGraph workflow code."""

    def create_agent(
        self,
        process: Process,
        config: DeploymentConfig,
        name: Optional[str] = None,
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

    def generate_langgraph_code(
        self,
        process: Process,
        config: DeploymentConfig,
        agent_name: str,
    ) -> GeneratedAgentCode:
        """Generates runnable Python LangGraph workflow code with state schema and HITL checkpoints."""
        clean_name = "".join(c for c in process.name if c.isalnum())
        tools: list[str] = []
        node_definitions: list[str] = []
        edge_connections: list[str] = []

        step_names = [act.name for act in process.activities]

        for index, step in enumerate(step_names):
            node_slug = "".join(c if c.isalnum() else "_" for c in step.lower()).strip("_")
            is_deployed = step in config.enabled_steps if config.enabled_steps else True

            # Identify if step is critical / needs human signoff
            is_hitl = config.approval_required and (index == len(step_names) - 1 or "confirm" in node_slug or "pay" in node_slug or "approval" in node_slug)

            if is_deployed and not is_hitl:
                node_code = f"""
def node_{node_slug}(state: WorkflowState) -> dict:
    \"\"\"Automated Step: {step}\"\"\"
    context = state.get("payload", {{}})
    # Execute LLM-driven structured tool invocation
    result = execute_agent_step(step_name="{step}", context=context)
    history = state.get("step_history", [])
    history.append({{"step": "{step}", "status": "automated", "result": result}})
    return {{"step_history": history, "current_step": "{step}"}}
"""
            else:
                node_code = f"""
def node_{node_slug}(state: WorkflowState) -> dict:
    \"\"\"Human-in-the-Loop Gate: {step}\"\"\"
    context = state.get("payload", {{}})
    # Gated checkpoint: awaits operator verification or CSM signoff
    approval_record = request_human_approval(step_name="{step}", context=context)
    history = state.get("step_history", [])
    history.append({{"step": "{step}", "status": "human_approved", "record": approval_record}})
    return {{"step_history": history, "current_step": "{step}"}}
"""
            node_definitions.append(node_code.strip())
            tools.append(f"tool_{node_slug}")

        # Build sequence edges
        for i in range(len(step_names) - 1):
            curr_slug = "".join(c if c.isalnum() else "_" for c in step_names[i].lower()).strip("_")
            next_slug = "".join(c if c.isalnum() else "_" for c in step_names[i+1].lower()).strip("_")
            edge_connections.append(f'workflow.add_edge("node_{curr_slug}", "node_{next_slug}")')

        first_slug = "".join(c if c.isalnum() else "_" for c in step_names[0].lower()).strip("_") if step_names else "init"
        last_slug = "".join(c if c.isalnum() else "_" for c in step_names[-1].lower()).strip("_") if step_names else "finish"

        full_code = f'''"""Autonomously generated LangGraph agent workflow for {process.name}."""

from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
import operator

class WorkflowState(TypedDict):
    case_id: str
    payload: Dict[str, Any]
    current_step: str
    step_history: Annotated[List[Dict[str, Any]], operator.add]
    is_escalated: bool

class HumanApprovalRequired(Exception):
    """Raised at a HITL checkpoint; catch it to persist a pending-approval record."""
    def __init__(self, step_name: str, context: dict, message: str = "Human approval required"):
        super().__init__(message)
        self.step_name = step_name
        self.context = context
        self.message = message

def execute_agent_step(step_name: str, context: dict) -> dict:
    # Wire this adapter to your real tool integrations (CRM, ITSM, ERP...).
    # It deliberately has no default success value: an unimplemented step must
    # fail loudly instead of pretending the work happened.
    raise NotImplementedError(
        f"No tool integration is configured for step '{{step_name}}'. "
        "Implement execute_agent_step before running this workflow."
    )

def request_human_approval(step_name: str, context: dict) -> dict:
    # Real Human-in-the-Loop gate: this checkpoint HALTS the branch until a
    # human approves it out-of-band (API/Slack). It never self-approves.
    raise HumanApprovalRequired(
        step_name=step_name,
        context=context,
        message=f"Workflow paused: step '{{step_name}}' requires human approval.",
    )

# ── Node Definitions ────────────────────────────────────────────────────────
{chr(10).join(node_definitions)}

# ── State Graph Assembly ───────────────────────────────────────────────────
def build_agent_graph() -> StateGraph:
    workflow = StateGraph(WorkflowState)

    # Register nodes
    {_indent_join([f'workflow.add_node("node_{"".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")}", node_{"".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")})' for s in step_names])}

    # Set entry point
    workflow.set_entry_point("node_{first_slug}")

    # Register linear and conditional edges
    {_indent_join(edge_connections)}
    workflow.add_edge("node_{last_slug}", END)

    return workflow.compile()

# Standalone execution entrypoint
app = build_agent_graph()
'''

        return GeneratedAgentCode(
            process_id=process.id,
            agent_name=agent_name,
            python_code=full_code,
            tools=tools,
            entrypoint="app = build_agent_graph()",
            langgraph_spec={
                "nodes_count": len(step_names),
                "edges_count": len(edge_connections),
                "entrypoint_node": f"node_{first_slug}",
                "terminal_node": f"node_{last_slug}",
            },
        )
