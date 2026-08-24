"""Deployment API with a deliberate human approval boundary.

Every state transition is recorded in the agent's audit trail (who acted,
when) so approvals are traceable -- an approval without an actor is not an
approval. Transitions are explicit and guarded: approve only from
pending_approval, resume only from paused, stop from running/paused.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import database
from ..deployment.agent_factory import AgentFactory
from ..models.schema import AgentBranch, AgentStatus, DeploymentConfig, DeploymentMode
from ..security import require_api_key

router = APIRouter()

_factory = AgentFactory()

ACTOR_HEADER = "X-Acting-User"


class DeployAgentRequest(BaseModel):
    process_id: str
    name: str = Field(min_length=3, max_length=80)
    config: DeploymentConfig


class DraftRequest(BaseModel):
    source_text: str = Field(min_length=8, max_length=5000)


def _actor(request: Request) -> str:
    """Who did this? Optional header; anonymous is recorded AS anonymous.

    The audit value is honesty about what we know, not identity enforcement:
    a missing name must be visible in the trail, never silently defaulted to
    something that looks accountable.
    """
    return request.headers.get(ACTOR_HEADER, "").strip() or "anonymous"


def _audit(agent: AgentBranch, action: str, actor: str) -> None:
    trail = agent.metrics.setdefault("audit", [])
    if not isinstance(trail, list):
        trail = []
        agent.metrics["audit"] = trail
    trail.append({
        "action": action,
        "actor": actor,
        "at": datetime.now(UTC).isoformat(),
        "from_status": agent.status.value,
    })


def _ensure_safe_config(config: DeploymentConfig) -> None:
    # The approval boundary is structural: no API caller can disable it, and
    # fully autonomous operation is not offered through this surface at all.
    if config.mode == DeploymentMode.AUTONOMOUS:
        raise HTTPException(
            status_code=422,
            detail="AUTONOMOUS mode is not available through this API. Use DRAFT or ASSISTED.",
        )
    if not config.approval_required:
        raise HTTPException(
            status_code=422,
            detail="approval_required cannot be disabled — every agent branch keeps a mandatory human approval gate.",
        )


@router.post("/deploy", response_model=AgentBranch, status_code=201,
             dependencies=[Depends(require_api_key)])
async def deploy_agent(request: DeployAgentRequest, http: Request) -> AgentBranch:
    process = await database.get_process(request.process_id)
    score = await database.get_score(request.process_id)
    if not process or not score:
        raise HTTPException(status_code=404, detail="Process or evidence-backed score not found")
    _ensure_safe_config(request.config)
    if not request.config.enabled_steps:
        request.config.enabled_steps = score.eligible_steps[:1]
    invalid = set(request.config.enabled_steps) - set(score.eligible_steps)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"These steps are not eligible for draft automation: {', '.join(sorted(invalid))}",
        )
    agent = AgentBranch(
        id=f"agent-{uuid4().hex[:10]}",
        process_id=request.process_id,
        name=request.name,
        status=AgentStatus.PENDING_APPROVAL,
        config=request.config,
        created_at=datetime.now(UTC),
        metrics={"drafts_created": 0, "human_approval_rate": None, "external_actions": 0},
    )
    _audit(agent, "deploy", _actor(http))
    # Generate the LangGraph program at deploy time and prove it parses before
    # storing it. The generated code is inert by design (execute_agent_step
    # raises until a human wires tools), but it must never be syntactically
    # broken -- a stored artifact that cannot compile is worse than none.
    agent.generated_code = _factory.generate_langgraph_code(
        process, request.config, request.name,
    )
    try:
        # compile() is stricter than parse(): it rejects anything that would
        # only fail at first execution of a statement.
        compile(agent.generated_code.python_code, "<generated>", "exec")
    except SyntaxError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Generated workflow failed validation: {error}",
        ) from error
    return await database.create_agent(agent)


@router.get("/", response_model=list[AgentBranch])
async def list_agents() -> list[AgentBranch]:
    return await database.get_agents()


@router.get("/{agent_id}", response_model=AgentBranch)
async def get_agent(agent_id: str) -> AgentBranch:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/approve", response_model=AgentBranch,
             dependencies=[Depends(require_api_key)])
async def approve_agent(agent_id: str, http: Request) -> AgentBranch:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Only a pending_approval agent can be approved (current: {agent.status.value}).",
        )
    _ensure_safe_config(agent.config)
    actor = _actor(http)
    _audit(agent, "approve", actor)
    agent.metrics["approved_by"] = actor
    agent.metrics["approved_at"] = datetime.now(UTC).isoformat()
    agent.status = AgentStatus.RUNNING
    return await database.save_agent(agent)


@router.post("/{agent_id}/pause", response_model=AgentBranch,
             dependencies=[Depends(require_api_key)])
async def pause_agent(agent_id: str, http: Request) -> AgentBranch:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Only a running agent can be paused (current: {agent.status.value}).",
        )
    _audit(agent, "pause", _actor(http))
    agent.status = AgentStatus.PAUSED
    return await database.save_agent(agent)


@router.post("/{agent_id}/resume", response_model=AgentBranch,
             dependencies=[Depends(require_api_key)])
async def resume_agent(agent_id: str, http: Request) -> AgentBranch:
    """Paused -> Running. Re-validation still applies: the approval gate can
    never have been switched off while the agent sat paused."""
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Only a paused agent can be resumed (current: {agent.status.value}).",
        )
    _ensure_safe_config(agent.config)
    _audit(agent, "resume", _actor(http))
    agent.status = AgentStatus.RUNNING
    return await database.save_agent(agent)


@router.post("/{agent_id}/stop", response_model=AgentBranch,
             dependencies=[Depends(require_api_key)])
async def stop_agent(agent_id: str, http: Request) -> AgentBranch:
    """Terminal state: running/paused -> stopped. A stopped agent cannot be
    resumed; redeploy a fresh branch instead."""
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status not in (AgentStatus.RUNNING, AgentStatus.PAUSED):
        raise HTTPException(
            status_code=409,
            detail=f"Only running or paused agents can be stopped (current: {agent.status.value}).",
        )
    _audit(agent, "stop", _actor(http))
    agent.status = AgentStatus.STOPPED
    return await database.save_agent(agent)


@router.post("/{agent_id}/draft", dependencies=[Depends(require_api_key)])
async def draft_response(agent_id: str, request: DraftRequest, http: Request) -> dict[str, str]:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Approve this agent before creating a draft")
    # There is intentionally no connector write call. This represents an item in a
    # review queue, not an outbound message.
    agent.metrics["drafts_created"] = int(agent.metrics.get("drafts_created", 0)) + 1
    _audit(agent, "draft_requested", _actor(http))
    await database.save_agent(agent)
    return {
        "status": "pending_human_review",
        "requested_by": _actor(http),
        "draft": "Thanks for the update. We have reviewed the request and will share the next confirmed step shortly.",
        "source_preview": request.source_text[:160],
        "safety_note": "No external message was sent. A human reviewer must approve any outbound action.",
    }


@router.get("/{agent_id}/audit-chain")
async def agent_audit_chain(agent_id: str) -> dict:
    """Tamper-evident export of the agent's audit trail (hash-chained)."""
    from ..export.audit_chain import export_agent_chain

    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    events = agent.metrics.get("audit") or []
    if not isinstance(events, list):
        events = []
    return export_agent_chain(agent.id, events)


@router.delete("/{agent_id}", dependencies=[Depends(require_api_key)])
async def undeploy_agent(agent_id: str, http: Request) -> dict[str, str]:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _audit(agent, "deleted", _actor(http))
    await database.delete_agent(agent_id)
    return {"message": "Draft agent removed; no external action was performed."}
