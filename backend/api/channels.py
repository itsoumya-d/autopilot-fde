import hmac
import json
import os
import re
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .. import database
from ..ingestion.slack_connector import SlackConfigurationError, sync_channel
from ..ingestion.whatsapp_connector import parse_webhook_payload
from ..models.schema import Channel, ChannelPublic, ChannelStatus, ChannelType, Message
from ..security import (
    require_api_key,
    verify_slack_signature,
    verify_whatsapp_signature,
)
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


@router.post("/email/sync", dependencies=[Depends(require_api_key)])
async def sync_email() -> dict[str, int | str]:
    """Poll the configured IMAP mailbox read-only, then rediscover."""
    from ..ingestion.email_connector import EmailConfigurationError, sync_email_messages

    try:
        messages = await sync_email_messages()
    except EmailConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    processes, activities = await run_discovery()
    return {"message": "Read-only email sync completed", "messages_seen": len(messages),
            "processes": processes, "activities": activities}


@router.get("/{channel_id}", response_model=ChannelPublic)
async def get_channel(channel_id: str) -> Channel:
    channel = await database.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.get("/{channel_id}/messages", response_model=list[Message])
async def list_channel_messages(
    channel_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[Message]:
    """Paginated message history for one channel, chronological order."""
    if not await database.get_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    return await database.get_messages(channel_id, limit=limit, offset=offset)


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
    # compare_digest, not ==: the handshake endpoint is unauthenticated by
    # design, so its token check must not leak timing information.
    if (
        mode == "subscribe"
        and challenge is not None
        and token is not None
        and hmac.compare_digest(token.encode(), expected.encode())
    ):
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


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON keys instead of silently taking the last value."""
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _decode_slack_interaction(raw: bytes, content_type: str) -> dict:
    """Decode Slack's form payload or the explicit legacy JSON envelope.

    The caller must verify the signature over raw bytes BEFORE calling this.
    Slack wire contract: https://docs.slack.dev/interactivity/handling-user-interaction/
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type not in ("application/x-www-form-urlencoded", "application/json", ""):
        raise HTTPException(status_code=415, detail="Use Slack form encoding or a JSON payload envelope")
    try:
        body = raw.decode("utf-8")
        if media_type == "application/x-www-form-urlencoded":
            if re.search(r"%(?![0-9a-fA-F]{2})", body):
                raise ValueError("Malformed percent encoding")
            fields = parse_qs(body, keep_blank_values=True, strict_parsing=True,
                              encoding="utf-8", errors="strict")
            if "payload" not in fields or any(len(values) != 1 for values in fields.values()):
                raise ValueError("Exactly one payload field is required")
            payload = fields["payload"][0]
        else:
            envelope = json.loads(body, object_pairs_hook=_unique_json_object)
            if not isinstance(envelope, dict):
                raise ValueError("Payload envelope must be an object")
            payload = envelope.get("payload")
        interactive = json.loads(payload, object_pairs_hook=_unique_json_object) if isinstance(payload, str) else payload
    except (ValueError, UnicodeError) as error:
        raise HTTPException(status_code=422, detail="Malformed interactive payload") from error
    if not isinstance(interactive, dict):
        raise HTTPException(status_code=422, detail="Interactive payload must be an object")
    return interactive


@router.post("/slack/interactive")
async def slack_interactive(request: Request) -> dict[str, str]:
    """One-click human approvals from Slack buttons (interactive payloads).

    Slack sends form-encoded JSON in a single ``payload`` field. The existing
    JSON envelope remains supported for local clients. Signatures use the exact
    raw body before either decoder runs. Configure SLACK_SIGNING_SECRET before
    exposing this local-demo route; signature absence behavior is unchanged.

    Button value format: ``approve:{agent_id}``. State and activation policy
    match REST approval; the audit label prefers the Slack user ID, falling back
    to the legacy name or explicit anonymous label. This does not provide a
    per-user authorization system or execute a worker.
    """
    from datetime import UTC, datetime

    from ..models.schema import AgentStatus as _AS

    raw = await request.body()
    verify_slack_signature(request, raw)
    interactive = _decode_slack_interaction(raw, request.headers.get("Content-Type", ""))
    if "type" in interactive and interactive["type"] != "block_actions":
        raise HTTPException(status_code=422, detail="Unsupported interaction type")
    actions = interactive.get("actions")
    if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], dict):
        raise HTTPException(status_code=422, detail="Exactly one approval action is required")
    action = actions[0]
    if action.get("action_id") != "agent_approve":
        raise HTTPException(status_code=422, detail="Unsupported action_id")
    value = action.get("value")
    if not isinstance(value, str) or not value.startswith("approve:") or not value.removeprefix("approve:").strip():
        raise HTTPException(status_code=422, detail="Unsupported action value")
    agent_id = value.split(":", 1)[1]
    user = interactive.get("user", {})
    if not isinstance(user, dict) or any(key in user and not isinstance(user[key], str) for key in ("id", "name")):
        raise HTTPException(status_code=422, detail="Interaction user must contain string identity fields")
    actor = f"slack:{user.get('id', '').strip() or user.get('name', '').strip() or 'anonymous'}"

    agent = await database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != _AS.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Only a pending_approval agent can be approved "
                   f"(current: {agent.status.value}).")
    # Keep the same activation policy as the REST approval surface. This
    # validates configuration before touching status, metrics or the audit log.
    from .agents import _ensure_safe_config

    _ensure_safe_config(agent.config)
    trail = agent.metrics.setdefault("audit", [])
    if not isinstance(trail, list):
        agent.metrics["audit"] = trail = []
    trail.append({"action": "approve", "actor": actor,
                  "at": datetime.now(UTC).isoformat(),
                  "from_status": agent.status.value})
    agent.metrics["approved_by"] = actor
    agent.metrics["approved_at"] = datetime.now(UTC).isoformat()
    agent.status = _AS.RUNNING
    await database.save_agent(agent)
    return {"status": "approved", "agent_id": agent.id, "actor": actor}
