import os

from fastapi import APIRouter, Depends, HTTPException

from .. import database
from ..models.schema import Process
from ..security import require_api_key
from ..services import run_discovery

router = APIRouter()


@router.get("/", response_model=list[Process])
async def list_processes() -> list[Process]:
    return await database.get_processes()


@router.post("/discover", dependencies=[Depends(require_api_key)])
async def trigger_discovery() -> dict[str, int | str]:
    processes, activities = await run_discovery()
    return {"message": "Discovery completed from read-only observations",
            "processes": processes, "activities": activities}


@router.get("/object-log")
async def object_log(limit: int = 500) -> dict:
    """OCEL 2.0-shaped multi-object event log over all mined activity.

    Events reference typed objects (case, actor, ticket, vendor, amount,
    email-domain) with qualified relationships; deterministic extraction, no
    LLM in the path.
    """
    from ..discovery.object_centric import build_object_log

    activities = [
        activity
        for process in await database.get_processes()
        for activity in process.activities
    ][: max(0, limit)]
    messages = await database.get_messages()
    return build_object_log(activities, messages)


@router.get("/object-alerts")
async def object_alerts(limit: int = 500) -> dict:
    """Deterministic governance alerts over the multi-object log."""
    from ..discovery.alerts import evaluate_alerts
    from ..discovery.object_centric import build_object_log

    activities = [
        activity
        for process in await database.get_processes()
        for activity in process.activities
    ][: max(0, limit)]
    messages = await database.get_messages()
    log = build_object_log(activities, messages)
    alerts = evaluate_alerts(log)
    return {
        "count": len(alerts),
        "policy_source": os.getenv("AUTOPILOT_ALERTS_POLICY", "") or "defaults",
        "alerts": alerts,
    }


@router.get("/{process_id}", response_model=Process)
async def get_process(process_id: str) -> Process:
    process = await database.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


@router.get("/{process_id}/timeline")
async def process_timeline(process_id: str) -> list[dict[str, object]]:
    process = await database.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return [
        {
            "activity_id": activity.id,
            "name": activity.name,
            "timestamp": activity.timestamp.isoformat(),
            "actors": activity.actors,
            "confidence": activity.confidence,
            "evidence": activity.evidence,
        }
        for activity in sorted(process.activities, key=lambda item: item.timestamp)
    ]
