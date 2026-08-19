from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .. import database
from ..ingestion.slack_connector import SlackConfigurationError, sync_channel
from ..models.schema import Channel, ChannelStatus
from ..services import run_discovery

router = APIRouter()


class SlackSyncRequest(BaseModel):
    slack_channel_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(default="Slack workspace", min_length=2, max_length=100)


@router.get("/", response_model=list[Channel])
async def list_channels() -> list[Channel]:
    return await database.get_channels()


@router.post("/slack/sync")
async def sync_slack(request: SlackSyncRequest) -> dict[str, int | str]:
    """Fetch Slack history using a server-side read-only bot token, then rediscover."""
    channel_id = f"slack:{request.slack_channel_id}"
    try:
        messages = await sync_channel(request.slack_channel_id, channel_id)
    except SlackConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    await database.upsert_channel(Channel(id=channel_id, name=request.display_name, status=ChannelStatus.ACTIVE))
    await database.create_messages(messages)
    processes, activities = await run_discovery()
    return {"message": "Read-only Slack sync completed", "messages_seen": len(messages), "processes": processes, "activities": activities}


@router.get("/{channel_id}", response_model=Channel)
async def get_channel(channel_id: str) -> Channel:
    channel = await database.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel
