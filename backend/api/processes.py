from fastapi import APIRouter, HTTPException

from .. import database
from ..models.schema import Process
from ..services import run_discovery

router = APIRouter()


@router.get("/", response_model=list[Process])
async def list_processes() -> list[Process]:
    return await database.get_processes()


@router.post("/discover")
async def trigger_discovery() -> dict[str, int | str]:
    processes, activities = await run_discovery()
    return {"message": "Discovery completed from read-only observations", "processes": processes, "activities": activities}


@router.get("/{process_id}", response_model=Process)
async def get_process(process_id: str) -> Process:
    process = await database.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


@router.get("/{process_id}/timeline")
async def process_timeline(process_id: str) -> list[dict[str, object]]:
    process = await get_process(process_id)
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
