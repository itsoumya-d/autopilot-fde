"""Explicit ingestion operations; there is no background polling in the MVP."""

from .. import database
from ..models.schema import Channel, ChannelStatus
from ..services import run_discovery
from .slack_connector import sync_channel


class IngestionPipeline:
    async def sync_slack(self, slack_channel_id: str, display_name: str) -> dict[str, int]:
        channel_id = f"slack:{slack_channel_id}"
        observations = await sync_channel(slack_channel_id, channel_id)
        await database.upsert_channel(Channel(id=channel_id, name=display_name, status=ChannelStatus.ACTIVE))
        await database.create_messages(observations)
        processes, activities = await run_discovery()
        return {"messages_seen": len(observations), "processes": processes, "activities": activities}
