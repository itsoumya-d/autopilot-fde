"""Deployment API with a deliberate human approval boundary."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database
from ..models.schema import AgentBranch, AgentStatus, DeploymentConfig, DeploymentMode

router = APIRouter()


class DeployAgentRequest(BaseModel):
    process_id: str
    name: str = Field(min_length=3, max_length=80)
    config: DeploymentConfig


class DraftRequest(BaseModel):
    source_text: str = Field(min_length=8, max_length=5000)


def _ensure_safe_config(config: DeploymentConfig) -> None:
    if not config.approval_required or config.mode != DeploymentMode.DRAFT:
        raise HTTPException(
            status_code=422,
            detail="This MVP only supports draft mode with a mandatory human approval gate.",
        )


@router.post("/deploy", response_model=AgentBranch, status_code=201)
async def deploy_agent(request: DeployAgentRequest) -> AgentBranch:
    process = await database.get_process(request.process_id)
    score = await database.get_score(request.process_id)
    if not process or not score:
        raise HTTPException(status_code=404, detail="Process or evidence-backed score not found")
    _ensure_safe_config(request.config)
    if not request.config.enabled_steps:
        request.config.enabled_steps = score.eligible_steps[:1]
    invalid = set(request.config.enabled_steps) - set(score.eligible_steps)
    if invalid:
        raise HTTPException(status_code=422, detail=f"These steps are not eligible for draft automation: {', '.join(sorted(invalid))}")
    agent = AgentBranch(
        id=f"agent-{uuid4().hex[:10]}",
        process_id=request.process_id,
        name=request.name,
        status=AgentStatus.PENDING_APPROVAL,
        config=request.config,
        created_at=datetime.now(timezone.utc),
        metrics={"drafts_created": 0, "human_approval_rate": None, "external_actions": 0},
    )
    return await database.create_agent(agent)


@router.get("/", response_model=list[AgentBranch])
async def list_agents() -> list[AgentBranch]:
    return await database.get_agents()


@router.post("/{agent_id}/approve", response_model=AgentBranch)
async def approve_agent(agent_id: str) -> AgentBranch:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _ensure_safe_config(agent.config)
    agent.status = AgentStatus.RUNNING
    return await database.save_agent(agent)


@router.post("/{agent_id}/pause", response_model=AgentBranch)
async def pause_agent(agent_id: str) -> AgentBranch:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.PAUSED
    return await database.save_agent(agent)


@router.post("/{agent_id}/draft")
async def draft_response(agent_id: str, request: DraftRequest) -> dict[str, str]:
    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Approve this agent before creating a draft")
    # There is intentionally no connector write call. This represents an item in a
    # review queue, not an outbound message.
    agent.metrics["drafts_created"] = int(agent.metrics.get("drafts_created", 0)) + 1
    await database.save_agent(agent)
    return {
        "status": "pending_human_review",
        "draft": "Thanks for the update. We have reviewed the request and will share the next confirmed step shortly.",
        "source_preview": request.source_text[:160],
        "safety_note": "No external message was sent. A human reviewer must approve any outbound action.",
    }


@router.delete("/{agent_id}")
async def undeploy_agent(agent_id: str) -> dict[str, str]:
    if not await database.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Draft agent removed; no external action was performed."}
