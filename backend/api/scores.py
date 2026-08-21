from ..security import require_api_key
from fastapi import APIRouter, Depends, HTTPException, Query

import asyncio

from .. import database
from ..models.schema import APScore, Recommendation, SimulationResult
from ..scoring.recommender import Recommender
from ..scoring.simulator import ProcessSimulator
from ..services import run_discovery

router = APIRouter()


@router.get("/", response_model=list[APScore])
async def list_scores() -> list[APScore]:
    return await database.get_scores()


@router.get("/recommendations", response_model=list[Recommendation])
async def recommendations() -> list[Recommendation]:
    return Recommender().recommend(await database.get_processes(), await database.get_scores())


@router.post("/recalculate", dependencies=[Depends(require_api_key)])
async def recalculate_scores() -> dict[str, int | str]:
    processes, _ = await run_discovery()
    return {"message": "Scores recalculated from current evidence", "processes": processes}


@router.get("/{process_id}", response_model=APScore)
async def get_score(process_id: str) -> APScore:
    score = await database.get_score(process_id)
    if not score:
        raise HTTPException(status_code=404, detail="No score exists for this process")
    return score


@router.get("/simulate/{process_id}", response_model=SimulationResult)
async def simulate_process(
    process_id: str,
    runs: int = Query(default=1000, ge=100, le=10000),
    confidence_threshold: float = Query(default=0.80, ge=0.5, le=0.99),
) -> SimulationResult:
    """Runs a Monte Carlo simulation of the workflow under agent deployment."""
    process = await database.get_process(process_id)
    score = await database.get_score(process_id)
    if not process or not score:
        raise HTTPException(status_code=404, detail="Process or score not found for simulation")
    
    simulator = ProcessSimulator()
    # The Monte Carlo loop is CPU-bound pure Python; offload it so the event
    # loop keeps serving other requests while 10k runs execute.
    return await asyncio.to_thread(
        simulator.simulate,
        process=process,
        score=score,
        runs=runs,
        confidence_threshold=confidence_threshold,
    )
