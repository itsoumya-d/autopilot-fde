"""Application service functions shared by the API and startup lifecycle."""

from . import database
from .demo_data import demo_channel, demo_messages
from .discovery.activity_extractor import ActivityExtractor
from .discovery.process_miner import ProcessMiner
from .scoring.aps_engine import APSEngine


async def ensure_demo_workspace() -> None:
    if await database.get_channels():
        return
    await database.upsert_channel(demo_channel())
    await database.create_messages(demo_messages())


async def run_discovery() -> tuple[int, int]:
    messages = await database.get_messages()
    activities = ActivityExtractor().extract(messages)
    processes = ProcessMiner().mine(activities)
    scores = [APSEngine().score(process) for process in processes]
    await database.replace_discovery_results(processes, scores)
    return len(processes), len(activities)
