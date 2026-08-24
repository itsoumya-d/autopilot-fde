import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .api import agents, channels, dashboard, dlq, processes, scores
from .mcp_http import router as mcp_http_router
from .security import api_key_configured, cors_origins_from_env
from .services import ensure_demo_workspace, run_discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autopilot")


@asynccontextmanager
async def lifespan(_: FastAPI):
    from .observability.export import configure_from_env

    await database.init_db()
    otel_status = configure_from_env()
    if not otel_status["enabled"]:
        logger.info("OTel OTLP export disabled: %s", otel_status.get("reason"))
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
    version="0.9.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    # Overridable via AUTOPILOT_CORS_ORIGINS (comma-separated). The default
    # covers only the local Next.js dev server; shared deployments must set it.
    allow_origins=cors_origins_from_env(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(processes.router, prefix="/api/processes", tags=["Processes"])
app.include_router(scores.router, prefix="/api/scores", tags=["Scoring"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(dlq.router, prefix="/api/dlq", tags=["DeadLetterQueue"])
app.include_router(mcp_http_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "mode": "safe-demo"}
