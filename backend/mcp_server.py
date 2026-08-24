"""Model Context Protocol server for AutoPilot FDE (stdio transport).

Lets any MCP-capable coding agent -- Claude Desktop, Claude Code, OpenAI
Codex CLI, Cursor, Windsurf -- read the discovered workspace and, when the
operator opts in, drive the deploy/approve lifecycle. One process speaks
newline-delimited JSON-RPC 2.0 on stdin/stdout; logs go to stderr only.

Tool policy, stated plainly:

- Read-only tools (discovery results, scores, simulations) are always
  available: they expose nothing the dashboard API does not.
- Mutating tools (discover, deploy, approve/pause/resume/stop) are refused
  unless the operator sets ``AUTOPILOT_MCP_ALLOW_MUTATIONS=1`` in the
  server's environment. The env var IS the authorization: it is configured
  by a human in the client config file, never passed through chat.
- The structural approval boundary is unchanged: AUTONOMOUS mode is not
  offered, approval_required cannot be disabled, and EXTERNAL_WRITE /
  CRITICAL_TRANSACTION steps remain human-gated in tool_adapters.

Wire the server into a client:

    Claude Desktop / Claude Code (claude_desktop_config.json):
        {"mcpServers": {"autopilot-fde": {
            "command": "python", "args": ["-m", "backend.mcp_server"],
            "cwd": "/path/to/autopilot-fde"}}}

    Codex CLI (~/.codex/config.toml):
        [mcp_servers.autopilot-fde]
        command = "python"
        args = ["-m", "backend.mcp_server"]
        cwd = "/path/to/autopilot-fde"
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_NAME = "autopilot-fde"
SERVER_VERSION = "0.7.0"

MUTATIONS_ENV = "AUTOPILOT_MCP_ALLOW_MUTATIONS"
MCP_ACTOR = "mcp-agent"

logger = logging.getLogger("autopilot.mcp")


# ── Workspace helpers ───────────────────────────────────────────────────────

def _configure_db_path() -> None:
    """Point the repository at AUTOPILOT_DB_PATH before first use.

    WAL mode (database.py) makes concurrent access with a running dashboard
    API safe; this only relocates which workspace file is opened.
    """
    override = os.getenv("AUTOPILOT_DB_PATH", "").strip()
    if override:
        from pathlib import Path

        import backend.database as database

        database.DB_PATH = Path(override).expanduser()


def mutations_allowed() -> bool:
    return os.getenv(MUTATIONS_ENV, "").strip() == "1"


class ToolError(Exception):
    """A tool failed for an explainable reason; surfaced as isError result."""


async def _require_process_and_score(process_id: str):
    from backend import database

    process = await database.get_process(process_id)
    score = await database.get_score(process_id)
    if not process or not score:
        raise ToolError(f"Process or evidence-backed score not found: {process_id}")
    return process, score


# ── Read-only tools ─────────────────────────────────────────────────────────

async def tool_dashboard_summary(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database

    return (await database.dashboard_summary()).model_dump()


async def tool_list_processes(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database

    processes = await database.get_processes()
    return {
        "count": len(processes),
        "processes": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "steps": [a.name for a in p.activities],
                "trace_count": p.metrics.trace_count,
            }
            for p in processes
        ],
    }


async def tool_get_process(args: dict[str, Any]) -> dict[str, Any]:
    process_id = str(args.get("process_id", "")).strip()
    if not process_id:
        raise ToolError("process_id is required")
    process = await _require_process_and_score(process_id)
    return process[0].model_dump(mode="json")


async def tool_get_scores(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database

    scores = await database.get_scores()
    return {"count": len(scores), "scores": [s.model_dump() for s in scores]}


async def tool_recommendations(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database
    from backend.scoring.recommender import Recommender

    recommendations = Recommender().recommend(
        await database.get_processes(), await database.get_scores()
    )
    return {"count": len(recommendations), "recommendations": [r.model_dump() for r in recommendations]}


async def tool_simulate_process(args: dict[str, Any]) -> dict[str, Any]:
    from backend.scoring.simulator import ProcessSimulator

    try:
        runs = int(args.get("runs", 1000))
        threshold = float(args.get("confidence_threshold", 0.80))
    except (TypeError, ValueError) as error:
        raise ToolError(f"Invalid numeric argument: {error}") from error
    if not 100 <= runs <= 10000:
        raise ToolError("runs must be between 100 and 10000")
    if not 0.5 <= threshold <= 0.99:
        raise ToolError("confidence_threshold must be between 0.5 and 0.99")

    process, score = await _require_process_and_score(str(args.get("process_id", "")).strip())
    # CPU-bound Monte Carlo loop stays off the event loop, same as the API.
    return (
        await asyncio.to_thread(
            ProcessSimulator().simulate,
            process=process,
            score=score,
            runs=runs,
            confidence_threshold=threshold,
        )
    ).model_dump()


async def tool_list_channels(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database

    channels = await database.get_channels()
    return {
        "count": len(channels),
        "channels": [
            {
                "id": c.id,
                "type": c.type.value,
                "name": c.name,
                "status": c.status.value,
                "message_count": c.message_count,
            }
            for c in channels
        ],
    }


async def tool_list_agents(_: dict[str, Any]) -> dict[str, Any]:
    from backend import database

    agents = await database.get_agents()
    return {
        "count": len(agents),
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "process_id": a.process_id,
                "status": a.status.value,
                "mode": a.config.mode.value,
            }
            for a in agents
        ],
    }


# ── Mutating tools (operator opt-in required) ───────────────────────────────

def _require_mutation_consent(tool_name: str) -> None:
    if mutations_allowed():
        return
    raise ToolError(
        f"Tool '{tool_name}' mutates the workspace and is disabled. A human must "
        f"set {MUTATIONS_ENV}=1 in this MCP server's environment (the client "
        "config file) to authorize deployments from a coding agent."
    )


async def tool_run_discovery(_: dict[str, Any]) -> dict[str, Any]:
    from backend.services import run_discovery

    processes, activities = await run_discovery()
    return {"message": "Discovery complete", "processes": processes, "activities": activities}


async def tool_deploy_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Mirrors POST /api/agents/deploy guards without FastAPI dependencies."""
    from uuid import uuid4

    from backend import database
    from backend.deployment.agent_factory import AgentFactory
    from backend.models.schema import AgentBranch, DeploymentConfig, DeploymentMode

    process_id = str(args.get("process_id", "")).strip()
    name = str(args.get("name", "")).strip()
    mode_raw = str(args.get("mode", "draft")).strip().lower()
    enabled_steps = args.get("enabled_steps") or []

    if not process_id:
        raise ToolError("process_id is required")
    if len(name) < 3 or len(name) > 80:
        raise ToolError("name must be 3-80 characters")

    process, score = await _require_process_and_score(process_id)
    try:
        mode = DeploymentMode(mode_raw)
    except ValueError as error:
        raise ToolError(f"Unknown mode '{mode_raw}'; use draft or assisted.") from error
    if mode == DeploymentMode.AUTONOMOUS:
        raise ToolError("AUTONOMOUS mode is not available; use draft or assisted.")

    config = DeploymentConfig(mode=mode, approval_required=True)
    if not enabled_steps:
        config.enabled_steps = score.eligible_steps[:1]
    else:
        invalid = set(enabled_steps) - set(score.eligible_steps)
        if invalid:
            raise ToolError(
                "These steps are not eligible for draft automation: "
                + ", ".join(sorted(invalid))
            )
        config.enabled_steps = list(enabled_steps)

    generated = AgentFactory().generate_langgraph_code(process, config, name)
    try:
        compile(generated.python_code, "<generated>", "exec")
    except SyntaxError as error:
        raise ToolError(f"Generated workflow failed validation: {error}") from error

    agent = AgentBranch(
        id=f"agent-{uuid4().hex[:10]}",
        process_id=process.id,
        name=name,
        config=config,
        metrics={
            "drafts_created": 0,
            "human_approval_rate": None,
            "external_actions": 0,
            "audit": [{
                "action": "deploy",
                "actor": MCP_ACTOR,
                "at": datetime.now(UTC).isoformat(),
                "from_status": "pending_approval",
            }],
        },
        generated_code=generated,
    )
    created = await database.create_agent(agent)
    return {
        "message": "Agent branch created; it stays pending_approval until a human approves.",
        "agent_id": created.id,
        "status": created.status.value,
        "enabled_steps": created.config.enabled_steps,
    }


async def _transition_agent(agent_id: str, action: str) -> dict[str, Any]:
    """Shared guarded transition logic mirroring api/agents.py."""
    from datetime import UTC, datetime

    from backend import database
    from backend.models.schema import AgentStatus

    allowed_from = {
        "approve": (AgentStatus.PENDING_APPROVAL,),
        "pause": (AgentStatus.RUNNING,),
        "resume": (AgentStatus.PAUSED,),
        "stop": (AgentStatus.RUNNING, AgentStatus.PAUSED),
    }
    agent = await database.get_agent(agent_id)
    if not agent:
        raise ToolError(f"Agent not found: {agent_id}")
    if agent.status not in allowed_from[action]:
        current = agent.status.value
        raise ToolError(
            f"Illegal transition: {action} requires "
            f"{[s.value for s in allowed_from[action]]}, current status is {current}."
        )
    trail = agent.metrics.setdefault("audit", [])
    if not isinstance(trail, list):
        agent.metrics["audit"] = trail = []
    trail.append({
        "action": action,
        "actor": MCP_ACTOR,
        "at": datetime.now(UTC).isoformat(),
        "from_status": agent.status.value,
    })
    if action == "approve":
        agent.metrics["approved_by"] = MCP_ACTOR
    agent.status = {
        "approve": AgentStatus.RUNNING,
        "pause": AgentStatus.PAUSED,
        "resume": AgentStatus.RUNNING,
        "stop": AgentStatus.STOPPED,
    }[action]
    await database.save_agent(agent)
    return {"agent_id": agent.id, "action": action, "status": agent.status.value}


async def tool_approve_agent(args: dict[str, Any]) -> dict[str, Any]:
    return await _transition_agent(_need_agent_id(args), "approve")


async def tool_pause_agent(args: dict[str, Any]) -> dict[str, Any]:
    return await _transition_agent(_need_agent_id(args), "pause")


async def tool_resume_agent(args: dict[str, Any]) -> dict[str, Any]:
    return await _transition_agent(_need_agent_id(args), "resume")


async def tool_stop_agent(args: dict[str, Any]) -> dict[str, Any]:
    return await _transition_agent(_need_agent_id(args), "stop")


def _need_agent_id(args: dict[str, Any]) -> str:
    agent_id = str(args.get("agent_id", "")).strip()
    if not agent_id:
        raise ToolError("agent_id is required")
    return agent_id


# ── Tool registry ───────────────────────────────────────────────────────────

_OBJECT = {"type": "object", "properties": {}, "additionalProperties": False}


def _schema(properties: dict[str, dict], required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


READ_TOOLS: list[dict[str, Any]] = [
    {
        "name": "dashboard_summary",
        "description": (
            "Aggregate AutoPilot FDE workspace summary: processes discovered, "
            "average APS, evidence-backed hours, active agents, pending approvals."
        ),
        "inputSchema": _OBJECT,
    },
    {
        "name": "list_processes",
        "description": "List business processes mined from communication streams, with steps and trace counts.",
        "inputSchema": _OBJECT,
    },
    {
        "name": "get_process",
        "description": "Full detail of one discovered process: activities, edges, metrics, safety notes.",
        "inputSchema": _schema({"process_id": {"type": "string"}}, ["process_id"]),
    },
    {
        "name": "get_scores",
        "description": (
            "Automation Potential Scores (APS) with factors, recommended "
            "modes, eligible/blocked steps, ROI estimates."
        ),
        "inputSchema": _OBJECT,
    },
    {
        "name": "recommendations",
        "description": "Deployment wave recommendations (Now/Next/Later) ranked by value and risk.",
        "inputSchema": _OBJECT,
    },
    {
        "name": "simulate_process",
        "description": (
            "Monte Carlo simulation of a process under automation: "
            "straight-through rate, escalations, bottleneck step, savings."
        ),
        "inputSchema": _schema({
            "process_id": {"type": "string"},
            "runs": {"type": "integer", "minimum": 100, "maximum": 10000},
            "confidence_threshold": {"type": "number", "minimum": 0.5, "maximum": 0.99},
        }, ["process_id"]),
    },
    {
        "name": "list_channels",
        "description": "Ingestion channels (Slack, WhatsApp, ...) with message counts.",
        "inputSchema": _OBJECT,
    },
    {
        "name": "list_agents",
        "description": "Deployed agent branches and their lifecycle statuses.",
        "inputSchema": _OBJECT,
    },
]

MUTATING_TOOLS: list[dict[str, Any]] = [
    {
        "name": "run_discovery",
        "description": f"MUTATING (needs {MUTATIONS_ENV}=1): re-run workflow discovery over all ingested messages.",
        "inputSchema": _OBJECT,
    },
    {
        "name": "deploy_agent",
        "description": (
            f"MUTATING (needs {MUTATIONS_ENV}=1): create a pending_approval "
            "LangGraph agent branch for a process. AUTONOMOUS mode is refused."
        ),
        "inputSchema": _schema({
            "process_id": {"type": "string"},
            "name": {"type": "string", "minLength": 3, "maxLength": 80},
            "mode": {"type": "string", "enum": ["draft", "assisted"]},
            "enabled_steps": {"type": "array", "items": {"type": "string"}},
        }, ["process_id", "name"]),
    },
    {
        "name": "approve_agent",
        "description": f"MUTATING (needs {MUTATIONS_ENV}=1): approve a pending agent; pending_approval -> running.",
        "inputSchema": _schema({"agent_id": {"type": "string"}}, ["agent_id"]),
    },
    {
        "name": "pause_agent",
        "description": f"MUTATING (needs {MUTATIONS_ENV}=1): pause a running agent.",
        "inputSchema": _schema({"agent_id": {"type": "string"}}, ["agent_id"]),
    },
    {
        "name": "resume_agent",
        "description": f"MUTATING (needs {MUTATIONS_ENV}=1): resume a paused agent.",
        "inputSchema": _schema({"agent_id": {"type": "string"}}, ["agent_id"]),
    },
    {
        "name": "stop_agent",
        "description": f"MUTATING (needs {MUTATIONS_ENV}=1): stop an agent (terminal state).",
        "inputSchema": _schema({"agent_id": {"type": "string"}}, ["agent_id"]),
    },
]

HANDLERS = {
    "dashboard_summary": tool_dashboard_summary,
    "list_processes": tool_list_processes,
    "get_process": tool_get_process,
    "get_scores": tool_get_scores,
    "recommendations": tool_recommendations,
    "simulate_process": tool_simulate_process,
    "list_channels": tool_list_channels,
    "list_agents": tool_list_agents,
    "run_discovery": tool_run_discovery,
    "deploy_agent": tool_deploy_agent,
    "approve_agent": tool_approve_agent,
    "pause_agent": tool_pause_agent,
    "resume_agent": tool_resume_agent,
    "stop_agent": tool_stop_agent,
}


def tools_listing() -> list[dict[str, Any]]:
    """Tool manifests; mutating descriptions carry their gate state inline."""
    enabled = mutations_allowed()
    listing = []
    for tool in READ_TOOLS + MUTATING_TOOLS:
        entry = dict(tool)
        if tool in MUTATING_TOOLS:
            state = "ENABLED" if enabled else "DISABLED"
            entry["description"] = (
                f"{entry['description']} [currently {state}: "
                f"set {MUTATIONS_ENV}=1 in the server environment to change]"
            )
        listing.append(entry)
    return listing


# ── JSON-RPC plumbing ───────────────────────────────────────────────────────

PARSE_ERROR, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32601, -32602, -32603


async def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatch one decoded JSON-RPC message. Returns a response or None."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if msg_id is None:
        return None  # notification
    try:
        if method == "initialize":
            requested = str(params.get("protocolVersion", PROTOCOL_VERSION))
            agreed = requested if requested in SUPPORTED_VERSIONS else PROTOCOL_VERSION
            return _ok(msg_id, {
                "protocolVersion": agreed,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method == "ping":
            return _ok(msg_id, {})
        if method == "tools/list":
            return _ok(msg_id, {"tools": tools_listing()})
        if method == "tools/call":
            return _ok(msg_id, await call_tool(params))
        return _error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")
    except ToolError as error:
        return _ok(msg_id, {"content": [_text(str(error))], "isError": True})
    except Exception as error:  # noqa: BLE001 - protocol boundary
        logger.exception("internal error handling %s", method)
        return _error(msg_id, INTERNAL_ERROR, f"Internal error: {error}")


def handle_message_sync(message: dict[str, Any]) -> dict[str, Any] | None:
    """Blocking wrapper for tests and scripted clients (no loop required)."""
    return asyncio.run(handle_message(message))


async def call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", ""))
    arguments = params.get("arguments") or {}
    handler = HANDLERS.get(name)
    if handler is None:
        raise ToolError(f"Unknown tool: {name}")
    if name in {t["name"] for t in MUTATING_TOOLS}:
        _require_mutation_consent(name)
    if not isinstance(arguments, dict):
        raise ToolError("arguments must be an object")
    payload = await handler(arguments)
    return {"content": [_text(json.dumps(payload, indent=2, default=str))]}


def _text(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def _ok(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


async def serve() -> None:
    """Read newline-delimited JSON-RPC on stdin; write responses on stdout."""
    from backend import database

    _configure_db_path()
    await database.init_db()
    loop = asyncio.get_running_loop()
    logger.info("autopilot-fde MCP server ready (mutations=%s)", mutations_allowed())
    try:
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                response = _error(None, PARSE_ERROR, "Parse error")
            else:
                if not isinstance(message, dict):
                    response = _error(None, PARSE_ERROR, "Parse error")
                else:
                    response = await handle_message(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, default=str) + "\n")
                sys.stdout.flush()
    finally:
        await database.close_db()
        logger.info("autopilot-fde MCP server stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(serve())


if __name__ == "__main__":  # pragma: no cover - stdio entrypoint
    main()
