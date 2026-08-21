import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .. import database
from ..ingestion.slack_connector import SlackConfigurationError, sync_channel
from ..ingestion.whatsapp_connector import parse_webhook_payload
from ..models.schema import Channel, ChannelPublic, ChannelStatus, ChannelType
from ..security import require_api_key, verify_whatsapp_signature
from ..services import run_discovery

router = APIRouter()


class SlackSyncRequest(BaseModel):
    slack_channel_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(default="Slack workspace", min_length=2, max_length=100)


@router.get("/", response_model=list[ChannelPublic])
async def list_channels() -> list[Channel]:
    return await database.get_channels()


@router.post("/slack/sync", dependencies=[Depends(require_api_key)])
async def sync_slack(request: SlackSyncRequest) -> dict[str, int | str]:
    """Fetch Slack history using a server-side read-only bot token, then rediscover."""
    channel_id = f"slack:{request.slack_channel_id}"
    try:
        messages = await sync_channel(request.slack_channel_id, channel_id)
    except SlackConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    await database.upsert_channel(Channel(
        id=channel_id, type=ChannelType.SLACK,
        name=request.display_name, status=ChannelStatus.ACTIVE))
    await database.create_messages(messages)
    processes, activities = await run_discovery()
    return {"message": "Read-only Slack sync completed", "messages_seen": len(messages),
            "processes": processes, "activities": activities}


@router.get("/{channel_id}", response_model=ChannelPublic)
async def get_channel(channel_id: str) -> Channel:
    channel = await database.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    """Meta webhook subscription handshake (GET with hub.* query params)."""
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WHATSAPP_VERIFY_TOKEN is not configured; webhook subscription is disabled.",
        )
    if mode == "subscribe" and token == expected and challenge is not None:
        return challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, int | str]:
    """Inbound WhatsApp Cloud API messages: persist read-only observations, rediscover.

    The raw body is signature-verified against WHATSAPP_APP_SECRET before any
    parsing, so unauthenticated posts cannot inject observations.
    """
    raw_body = await request.body()
    verify_whatsapp_signature(request, raw_body)

    import json as _json

    try:
        payload = _json.loads(raw_body or b"{}")
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Malformed JSON payload") from error

    messages = parse_webhook_payload(payload, expected_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"))
    if messages:
        await database.upsert_channel(Channel(
            id=messages[0].channel_id,
            type=ChannelType.WHATSAPP,
            name="WhatsApp Business",
            status=ChannelStatus.ACTIVE,
        ))
        await database.create_messages(messages)
        processes, activities = await run_discovery()
        return {"message": "WhatsApp messages ingested", "messages_seen": len(messages),
                "processes": processes, "activities": activities}
    return {"message": "No ingestible messages in payload", "messages_seen": 0}
