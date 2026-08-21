"""WhatsApp Cloud API ingestion.

Message intake is webhook-driven: Meta pushes inbound messages to
``POST /api/channels/whatsapp/webhook``. Parsing is available without
credentials so the pipeline can be exercised end-to-end in demo mode;
the optional ``WhatsAppConnector`` adds live health checks when real
credentials are configured.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from .base import ChannelConnector
from ..models.schema import ChannelType, Message

logger = logging.getLogger(__name__)

SUPPORTED_CONTENT_TYPES = {"text", "image", "document", "audio", "video", "sticker", "location"}


def parse_webhook_payload(
    payload: Dict[str, Any],
    expected_phone_number_id: str | None = None,
) -> List[Message]:
    """Parse an inbound WhatsApp Cloud API webhook payload into Messages.

    ``expected_phone_number_id`` filters entries to one WhatsApp business
    number when configured; when None, every entry is accepted so demo and
    multi-number setups still ingest.
    """
    messages: List[Message] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")

            if expected_phone_number_id and phone_number_id != expected_phone_number_id:
                continue

            for msg in value.get("messages", []):
                raw_ts = msg.get("timestamp")
                try:
                    timestamp = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
                except (TypeError, ValueError, OSError):
                    logger.warning("WhatsApp message %s had invalid timestamp %r", msg.get("id"), raw_ts)
                    timestamp = datetime.now(timezone.utc)

                sender = msg.get("from") or "unknown"
                msg_type = msg.get("type", "unknown")
                if msg_type == "text":
                    content = msg.get("text", {}).get("body", "")
                elif msg_type in SUPPORTED_CONTENT_TYPES:
                    content = f"[{msg_type} message]"
                else:
                    content = "[unsupported message type]"

                messages.append(Message(
                    id=msg.get("id") or f"wa:{uuid.uuid4()}",
                    channel_id=f"whatsapp:{phone_number_id or 'unknown'}",
                    sender=sender,
                    content=content,
                    timestamp=timestamp,
                    metadata={"whatsapp_type": msg_type, "read_only": True},
                ))
    return messages


class WhatsAppConnector(ChannelConnector):
    def __init__(self, config: Dict[str, str]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.phone_number_id = config.get("phone_number_id")
        self.verify_token = config.get("verify_token")  # For webhook setup

        if not self.access_token or not self.phone_number_id:
            raise ValueError("WhatsApp access_token and phone_number_id are required")

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    async def connect(self) -> bool:
        # Check if the token is valid by making a simple API call
        url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except httpx.HTTPError as error:
            logger.error("WhatsApp connect error: %s", error)
            return False

    async def health_check(self) -> bool:
        return await self.connect()

    async def fetch_messages(self, since: datetime) -> List[Message]:
        # WhatsApp Cloud API has no historical pull API: intake is push-only via
        # the registered webhook endpoint. History therefore accumulates in the
        # local store from the moment the webhook is connected.
        logger.info("WhatsApp intake is webhook-driven; fetch_messages is a no-op.")
        return []
