import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .api import agents, channels, dashboard, processes, scores
from .security import api_key_configured
from .services import ensure_demo_workspace, run_discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autopilot")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.init_db()
    if not api_key_configured():
        logger.warning(
            "AUTOPILOT_API_KEY is not set: mutating endpoints (deploy, approve, "
            "sync, discover) are OPEN. Set it before any shared deployment."
        )
    await ensure_demo_workspace()
    if not await database.get_processes():
        await run_discovery()
    yield
    await database.close_db()


app = FastAPI(
    title="AutoPilot FDE",
    description="Evidence-backed workflow discovery and human-approved draft automation.",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(processes.router, prefix="/api/processes", tags=["Processes"])
app.include_router(scores.router, prefix="/api/scores", tags=["Scoring"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "mode": "safe-demo"}
