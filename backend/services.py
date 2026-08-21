"""Application service functions shared by the API and startup lifecycle.

Discovery is synchronous CPU work (keyword extraction, trace clustering,
scoring). It runs inside ``asyncio.to_thread`` so a long mining pass cannot
stall the event loop while other requests are in flight.
"""

import asyncio
import logging
import os

from . import database
from .demo_data import demo_channel, demo_messages
from .discovery.activity_extractor import ActivityExtractor
from .discovery.process_miner import ProcessMiner
from .llm.enhancer import get_enhancer
from .scoring.aps_engine import APSEngine

logger = logging.getLogger(__name__)


async def ensure_demo_workspace() -> None:
    if await database.get_channels():
        return
    await database.upsert_channel(demo_channel())
    await database.create_messages(demo_messages())


def _discover_sync(messages) -> tuple[int, int]:
    """The CPU-bound pipeline, executed off the event loop."""
    activities = ActivityExtractor().extract(messages)
    processes = ProcessMiner().mine(activities)
    scores = [APSEngine().score(process) for process in processes]
    return activities, processes, scores


async def _maybe_enhance(processes) -> None:
    """Optional LLM enrichment behind AUTOPILOT_LLM_ENHANCE=1 + a key.

    Purely additive: when the enhancer is unconfigured or fails, discovery
    results are stored exactly as the deterministic engine produced them.
    enhance_processes mutates the Process models in place.
    """
    if os.getenv("AUTOPILOT_LLM_ENHANCE", "0") != "1":
        return
    try:
        enhancer = get_enhancer()
        await asyncio.to_thread(enhancer.enhance_processes, processes)
    except Exception:  # noqa: BLE001 - enrichment must never break discovery
        logger.exception("LLM enhancement failed; storing deterministic results")


async def run_discovery() -> tuple[int, int]:
    messages = await database.get_messages()
    activities, processes, scores = await asyncio.to_thread(_discover_sync, messages)
    await _maybe_enhance(processes)
    await database.replace_discovery_results(processes, scores)
    return len(processes), len(activities)
